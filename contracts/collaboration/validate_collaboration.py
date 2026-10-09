"""Checks design contracts and local development stubs, never actual video.

Standard library only; defaults to in-memory HTTP request/response streams.
Pass --http to also use a real temporary localhost server. The schema checker
covers the subset used by this kit, not the whole OpenAPI/JSON Schema standard.
"""
from copy import deepcopy
from http.client import HTTPResponse
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from contract_utils import EXAMPLES, ROOT, SPEC, validate
from mock_api import Handler, MockServer, MockState
from runtime_contracts import ModuleError, RenderRequest, RenderStub

spec = importlib.util.spec_from_file_location('data_validation', ROOT.parent / 'validate_examples.py')
data_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_validation)
USE_HTTP = '--http' in sys.argv
if USE_HTTP:
    sys.argv.remove('--http')


class MemoryConnection:
    """A byte-stream harness for the same Handler; no socket/network access."""
    def __init__(self, incoming):
        self.incoming = io.BytesIO(incoming)
        self.outgoing = bytearray()

    def makefile(self, *args, **kwargs):
        return self.incoming

    def sendall(self, data):
        self.outgoing.extend(data)


class ContractChecks(unittest.TestCase):
    def test_all_http_examples(self):
        self.assertEqual(len(EXAMPLES), 31)
        for name, example in EXAMPLES.items():
            with self.subTest(example=name):
                validate(example['response'], example['schema'])
                self.assertIs(example['response']['simulation'], True)
                if 'request' in example:
                    validate(example['request'], example['request_schema'])

    def test_copied_data_definitions_and_references(self):
        def remap(value):
            if isinstance(value, dict):
                return {key: val.replace('#/$defs/', '#/components/schemas/Data_')
                        if key == '$ref' else remap(val) for key, val in value.items()}
            if isinstance(value, list):
                return [remap(item) for item in value]
            return value

        for name, schema in data_validation.SCHEMA['$defs'].items():
            self.assertEqual(SPEC['components']['schemas']['Data_' + name], remap(schema))

        def resolve(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    self.assertTrue(value['$ref'].startswith('#/'))
                    target = SPEC
                    for key in value['$ref'][2:].split('/'):
                        target = target[key]
                for child in value.values():
                    resolve(child)
            elif isinstance(value, list):
                for child in value:
                    resolve(child)
        resolve(SPEC)

    def test_nine_second_timeline_and_asset_mapping(self):
        timeline = json.loads((ROOT / 'smoke9.timeline.json').read_text())
        assets = data_validation.check_assets(json.loads(
            (ROOT.parent / 'examples/assets.json').read_text()))
        data_validation.structural(timeline, data_validation.SCHEMA)
        data_validation.check_timeline(timeline, assets, supported=['core_v1'])
        data_validation.check_stage(timeline, 'MVP', assets)
        self.assertEqual(timeline['timeline']['duration_frames'], 270)
        paths = json.loads((ROOT / 'asset-paths.example.json').read_text())
        used = {shot['clip_id'] for shot in timeline['timeline']['shots']}
        used |= {track['asset_id'] for track in timeline['timeline']['audio_tracks']}
        used |= {overlay['text_style']['font_asset_id'] if overlay['kind'] == 'text'
                 else overlay['asset_id'] for overlay in timeline['timeline']['overlays']}
        self.assertLessEqual(used, paths.keys())

    def test_reject_incompatible_api_shapes(self):
        cases = [
            ('GenerateRequest', {'request_id': 'r1', 'settings': {'output': {}}}),
            ('EditRequest', {'request_id': 'r1', 'base_version_id': 'v1',
                'input': {'kind': 'instruction', 'text': 'warm', 'operations': []}}),
            ('EditRequest', {'request_id': 'r1', 'base_version_id': 'v1',
                'input': {'kind': 'operations', 'operations': []}}),
            ('EditRequest', {'request_id': 'r1', 'base_version_id': 'v1',
                'input': {'kind': 'operations', 'operations': [{'type': 'set_target_length', 'seconds': 20}]}}),
        ]
        missing = deepcopy(EXAMPLES['project_ready']['response'])
        del missing['project']['pending_selection']
        cases.append(('ProjectResponse', missing))
        for schema, value in cases:
            with self.subTest(schema=schema, value=value), self.assertRaises(ValueError):
                validate(value, schema)

    def test_render_stub_marks_simulation_and_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / 'fixture.bin'
            fixture.write_bytes(b'not-a-video: byte-copy test only')
            request = RenderRequest(json.loads((ROOT / 'smoke9.timeline.json').read_text()),
                                    {}, root / 'job', root / 'job/result.mp4', 120, lambda: False)
            progress = []
            result = RenderStub(fixture).render_timeline(request, progress.append)
            self.assertIs(result.simulation, True)
            self.assertEqual(result.output_path.read_bytes(), fixture.read_bytes())
            self.assertEqual([p.completed_frames for p in progress], [0, 270])
            with self.assertRaises(ModuleError) as error:
                RenderStub(fixture).render_timeline(request, progress.append)
            self.assertEqual(error.exception.code, 'OUTPUT_EXISTS')
            with self.assertRaises(ModuleError) as error:
                RenderStub(fail=True).render_timeline(request, progress.append)
            self.assertEqual(error.exception.code, 'RENDER_FAILED')
            cancelled = RenderRequest(request.timeline_document, {}, root, root / 'other.mp4', 120, lambda: True)
            with self.assertRaises(ModuleError) as error:
                RenderStub(fixture).render_timeline(cancelled, progress.append)
            self.assertEqual(error.exception.code, 'JOB_INTERRUPTED')
            with self.assertRaises(ModuleError) as error:
                RenderStub().render_timeline(request, progress.append)
            self.assertEqual(error.exception.code, 'FIXTURE_MEDIA_MISSING')


class MockChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.media = Path(self.directory.name) / 'fixture.bin'
        self.media.write_bytes(b'0123456789abcdef')  # HTTP byte test, not a codec test.
        if USE_HTTP:
            self.server = MockServer(('127.0.0.1', 0), media=self.media)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.base = f'http://127.0.0.1:{self.server.server_port}'
        else:
            self.server = MockState(media=self.media)
        self.project = '/api/projects/project_demo'

    def tearDown(self):
        if USE_HTTP:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)

    def request(self, path, body=None, *, expected=200, schema=None, raw=None, headers=None, method=None):
        headers = dict(headers or {})
        if body is not None:
            raw = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        method = method or ('POST' if raw is not None else 'GET')
        if USE_HTTP:
            request = Request(self.base + path, data=raw, headers=headers, method=method)
            try:
                response = urlopen(request, timeout=3)
            except HTTPError as error:
                response = error
        else:
            headers['Host'] = 'localhost'
            headers['Content-Length'] = str(len(raw or b''))
            wire = (f'{method} {path} HTTP/1.1\r\n' + ''.join(
                f'{key}: {value}\r\n' for key, value in headers.items()) + '\r\n').encode() + (raw or b'')
            connection = MemoryConnection(wire)
            Handler(connection, ('127.0.0.1', 0), self.server)
            response = HTTPResponse(MemoryConnection(bytes(connection.outgoing)), method=method)
            response.begin()
        with response:
            self.assertEqual(response.status, expected)
            self.assertEqual(response.headers['X-Auto-Vlog-Simulation'], 'true')
            content = response.read()
            if response.headers.get_content_type() == 'application/json' and method != 'HEAD':
                value = json.loads(content)
                self.assertIs(value['simulation'], True)
                if expected >= 400:
                    validate(value, 'ErrorResponse')
                elif schema:
                    validate(value, schema)
                return value
            return content, response.headers

    def start(self, request_id='g1'):
        return self.request(self.project + '/generate', {'request_id': request_id, 'settings': {}},
                            expected=202, schema='JobAccepted')['job_id']

    def finish(self, job_id, expected='done'):
        states = []
        for _ in range(3):
            job = self.request('/api/jobs/' + job_id, schema='JobResponse')['job']
            states.append(job['status'])
        self.assertEqual(states, ['queued', 'rendering', expected])
        project = self.request(self.project, schema='ProjectResponse')['project']
        self.assertIsNone(project['active_job_id'])
        return job

    def edit(self, base, request_id='e1', operation=None, text=None):
        value = {'kind': 'instruction', 'text': text} if text else {
            'kind': 'operations', 'operations': [operation or {'type': 'set_warmth', 'value': 0.25}]}
        return self.request(self.project + '/edits',
            {'request_id': request_id, 'base_version_id': base, 'input': value},
            expected=202, schema='JobAccepted')['job_id']

    def test_idempotency_busy_versions_and_stale_edit(self):
        self.request('/api/health', schema='HealthResponse')
        job_id = self.start()
        self.assertEqual(self.start(), job_id)  # Replay even while busy.
        conflict = self.request(self.project + '/generate',
            {'request_id': 'g1', 'settings': {'warmth_override': 0.4}}, expected=409)
        self.assertEqual(conflict['error']['code'], 'IDEMPOTENCY_CONFLICT')
        busy = self.request(self.project + '/generate', {'request_id': 'g2', 'settings': {}}, expected=409)
        self.assertEqual(busy['error']['code'], 'PROJECT_BUSY')
        first = self.finish(job_id)['version_id']
        self.assertEqual(self.start(), job_id)  # Replay even after a version exists.
        second = self.finish(self.edit(first))['version_id']
        self.assertEqual(self.request(self.project)['project']['settings']['warmth_override'], 0.25)
        stale = self.request(self.project + '/edits', {'request_id': 'e2', 'base_version_id': first,
            'input': {'kind': 'instruction', 'text': 'warm'}}, expected=409)
        self.assertEqual(stale['error']['code'], 'STALE_VERSION')
        versions = self.request(self.project + '/versions', schema='VersionsResponse')['versions']
        self.assertEqual([v['version_id'] for v in versions], [second, first])
        selected = self.request(self.project + '/current-version',
            {'request_id': 's1', 'base_version_id': second, 'version_id': first}, schema='ProjectResponse')
        self.assertEqual(selected['project']['current_version']['version_id'], first)
        self.assertEqual(selected['project']['settings'], versions[1]['settings'])

    def test_failure_and_interruption_keep_previous_success(self):
        version = self.finish(self.start())['version_id']
        for scenario in ('failed', 'interrupted'):
            self.server.scenario = scenario
            job = self.finish(self.edit(version, request_id=scenario), scenario)
            self.assertIsNotNone(job['error'])
            self.assertIsNone(job['version_id'])
            self.assertEqual(self.request(self.project)['project']['current_version']['version_id'], version)
        self.server.scenario = 'success'
        self.finish(self.edit(version, request_id='retry'))

    def test_ambiguous_edit_confirmation_and_title(self):
        self.server.scenario = 'needs_selection'
        version = self.finish(self.start())['version_id']
        job = self.finish(self.edit(version, text='delete that clip'), 'needs_selection')
        pending = self.request(self.project)['project']['pending_selection']
        self.assertEqual(pending['job_id'], job['job_id'])
        clip = job['resolution']['candidates'][0]['clip_id']
        version2 = self.finish(self.edit(version, 'confirmed', {'type': 'remove_clip', 'clip_id': clip}))['version_id']
        project = self.request(self.project)['project']
        self.assertIsNone(project['pending_selection'])
        self.assertIn(clip, project['settings']['excluded_clip_ids'])
        self.assertEqual(project['settings']['duration_policy']['mode'], 'natural')
        self.finish(self.edit(version2, 'title', {'type': 'set_title', 'field': 'headline', 'value': 'Campus Days'}))
        self.assertEqual(self.request(self.project)['project']['settings']['title_overrides']['headline'], 'Campus Days')

    def test_create_upload_and_boundary_independent_replay(self):
        project = self.request('/api/projects', {'request_id': 'p1'}, expected=201, schema='ProjectResponse')['project']
        self.project = '/api/projects/' + project['project_id']
        self.assertEqual(project['clips'], [])
        def upload(boundary, content=b'sample'):
            raw = (f'--{boundary}\r\nContent-Disposition: form-data; name="request_id"\r\n\r\nu1\r\n'
                   f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="phone.mp4"\r\n'
                   'Content-Type: video/mp4\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
            return raw, {'Content-Type': 'multipart/form-data; boundary=' + boundary}
        raw, headers = upload('BOUNDARY-A')
        result = self.request(self.project + '/clips', raw=raw, headers=headers, expected=201, schema='ClipResponse')
        raw, headers = upload('BOUNDARY-B')
        replay = self.request(self.project + '/clips', raw=raw, headers=headers, expected=201)
        self.assertEqual(replay, result)
        self.assertEqual(len(self.request(self.project)['project']['clips']), 1)
        raw, headers = upload('BOUNDARY-C', b'changed')
        self.assertEqual(self.request(self.project + '/clips', raw=raw, headers=headers, expected=409)['error']['code'],
                         'IDEMPOTENCY_CONFLICT')

    def test_media_byte_range_download_and_missing_fixture(self):
        job = self.finish(self.start())
        path = job['video_url']
        content, headers = self.request(path)
        self.assertEqual(content, self.media.read_bytes())
        content, headers = self.request(path, headers={'Range': 'bytes=2-5'}, expected=206)
        self.assertEqual(content, b'2345')
        self.assertEqual(headers['Content-Range'], 'bytes 2-5/16')
        content, headers = self.request(path, headers={'Range': 'bytes=-4'}, expected=206)
        self.assertEqual(content, b'cdef')
        self.request(path, headers={'Range': 'bytes=999-'}, expected=416)
        content, headers = self.request(path + '?download=true', method='HEAD')
        self.assertEqual(content, b'')
        self.assertEqual(headers['Content-Length'], '16')
        self.assertIn('attachment', headers['Content-Disposition'])
        self.server.media = None
        self.assertEqual(self.request(path, expected=404)['error']['code'], 'FIXTURE_MEDIA_MISSING')

    def test_validation_and_continuing_rendering(self):
        self.request(self.project + '/generate', {'request_id': 'bad', 'settings': {'output': {}}}, expected=422)
        self.server.scenario = 'rendering'
        job_id = self.start()
        for _ in range(5):
            job = self.request('/api/jobs/' + job_id, schema='JobResponse')['job']
        self.assertEqual(job['status'], 'rendering')
        self.assertEqual(self.request(self.project)['project']['active_job_id'], job_id)


if __name__ == '__main__':
    print('Transport: localhost HTTP' if USE_HTTP else 'Transport: in-memory HTTP bytes; socket binding/browser playback NOT tested.', flush=True)
    unittest.main(verbosity=2)
