"""Local single-project mock API. NO AI, FFmpeg, upload persistence or cloud.

python3 mock_api.py --port 8000 --scenario success --media /absolute/sample.mp4
All JSON responses and media responses explicitly identify simulation.
State is memory-only; restart resets it. Never publish this development server.
"""
import argparse
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs

from contract_utils import EXAMPLES, validate

META={'api_version':'1.0.0','simulation':True}
TERMINAL={'done','failed','interrupted','needs_selection'}


class ApiError(Exception):
    def __init__(self,status,code,message,retryable=False):
        self.status,self.code,self.message,self.retryable=status,code,message,retryable


class MockState:
    def __init__(self, scenario='success', media=None):
        self.scenario, self.media = scenario, Path(media).resolve() if media else None
        self.project=deepcopy(EXAMPLES['project_ready']['response']['project'])
        self.jobs={};self.polls={};self.versions={};self.replays={};self.next_job=1;self.next_version=1


class MockServer(HTTPServer, MockState):
    def __init__(self, address, scenario='success', media=None):
        HTTPServer.__init__(self, address, Handler)
        MockState.__init__(self, scenario, media)


class Handler(BaseHTTPRequestHandler):
    server: MockServer

    def log_message(self, format, *args):
        pass

    def send_json(self, status, data, schema=None, extra_headers=None):
        if schema:validate(data,schema)
        payload=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('X-Auto-Vlog-Simulation','true')
        self.send_header('Cache-Control','no-store')
        for k,v in (extra_headers or {}).items():self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(payload)

    def error(self, error):
        self.send_json(error.status,{**META,'error':{'code':error.code,'message':error.message,'retryable':error.retryable}},'ErrorResponse')

    def do_GET(self):self.dispatch()
    def do_POST(self):self.dispatch()
    def do_HEAD(self):self.dispatch()

    def dispatch(self):
        try:self.route()
        except ApiError as e:self.error(e)
        except (ValueError,KeyError,TypeError) as e:self.error(ApiError(422,'VALIDATION_ERROR',str(e)))

    def read_body(self):
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError:raise ApiError(400,'BAD_REQUEST','Content-Length 必须是整数')
        if n<0:raise ApiError(400,'BAD_REQUEST','Content-Length 不能为负数')
        if n>104857600+65536:raise ApiError(413,'UPLOAD_TOO_LARGE','模拟服务单次请求上限约 100 MiB')
        return self.rfile.read(n)

    def request_data(self, upload=False):
        raw=self.read_body()
        if upload:
            ct=self.headers.get('Content-Type','')
            if not ct.startswith('multipart/form-data;'):raise ApiError(400,'BAD_REQUEST','上传使用 multipart/form-data')
            message=BytesParser(policy=default).parsebytes(('Content-Type: '+ct+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
            if not message.is_multipart():raise ApiError(400,'BAD_REQUEST','无效 multipart boundary')
            parts={}
            for part in message.iter_parts():
                name=part.get_param('name',header='content-disposition')
                if name not in ('request_id','file') or name in parts:raise ApiError(422,'VALIDATION_ERROR','仅接受 request_id 和一个 file')
                parts[name]=part
            if set(parts)!={'request_id','file'}:raise ApiError(422,'VALIDATION_ERROR','缺少 request_id 或 file')
            content=parts['file'].get_payload(decode=True) or b''
            if not content:raise ApiError(422,'VALIDATION_ERROR','文件为空')
            if len(content)>104857600:raise ApiError(413,'UPLOAD_TOO_LARGE','单文件超过 100 MiB')
            request={'request_id':parts['request_id'].get_content().strip(),'file':parts['file'].get_filename() or 'sample.mp4'}
            validate(request,'UploadForm')
            fingerprint={**request,'sha256':hashlib.sha256(content).hexdigest()}
            return request,fingerprint
        try:request=json.loads(raw)
        except (ValueError,UnicodeError):raise ApiError(400,'BAD_REQUEST','请求必须是 JSON')
        if not isinstance(request,dict):raise ApiError(422,'VALIDATION_ERROR','请求必须是 JSON 对象')
        return request,request

    def route(self):
        url=urlparse(self.path);path=url.path;s=self.server
        if self.command in ('GET','HEAD'):
            if path=='/api/health':
                return self.send_json(200,deepcopy(EXAMPLES['health']['response']),'HealthResponse')
            if path.startswith('/api/jobs/'):
                jid=path.removeprefix('/api/jobs/')
                if jid not in s.jobs:raise ApiError(404,'NOT_FOUND','任务不存在')
                job=s.jobs[jid]
                if job['status'] not in TERMINAL:
                    s.polls[jid]+=1
                    step=s.polls[jid]
                    if step==2:
                        job.update(status='rendering',message='模拟：渲染中',progress={'completed':450,'total':900,'unit':'frames'})
                    if step>=3 and s.scenario!='rendering':self.finish_job(job)
                return self.send_json(200,{**META,'job':job},'JobResponse')
            prefix='/api/projects/'+s.project['project_id']
            if path==prefix:return self.send_json(200,{**META,'project':s.project},'ProjectResponse')
            if path==prefix+'/versions':
                current=s.project['current_version']
                return self.send_json(200,{**META,'project_id':s.project['project_id'],
                    'current_version_id':current['version_id'] if current else None,
                    'versions':list(reversed(list(s.versions.values())))},'VersionsResponse')
            video=re.fullmatch(re.escape(prefix)+r'/versions/([^/]+)/video',path)
            if video:
                if video.group(1) not in s.versions:raise ApiError(404,'NOT_FOUND','版本不存在')
                return self.send_media(parse_qs(url.query).get('download',['false'])[0]=='true')
            raise ApiError(404,'NOT_FOUND','模拟路由或资源不存在')

        if self.command!='POST':raise ApiError(405,'BAD_REQUEST','不支持的方法')
        prefix='/api/projects/'+s.project['project_id']
        schemas={'/api/projects':'CreateProjectRequest',prefix+'/clips':'UploadForm',prefix+'/generate':'GenerateRequest',
                 prefix+'/edits':'EditRequest',prefix+'/current-version':'SelectVersionRequest'}
        if path not in schemas:raise ApiError(404,'NOT_FOUND','模拟路由不存在')
        request,fingerprint=self.request_data(path.endswith('/clips'))
        validate(request,schemas[path])
        key=(path,request['request_id']); encoded=json.dumps(fingerprint,sort_keys=True,ensure_ascii=False)
        if key in s.replays:
            old,status,response,schema=s.replays[key]
            if old!=encoded:raise ApiError(409,'IDEMPOTENCY_CONFLICT','同一 request_id 对应不同内容')
            return self.send_json(status,response,schema)
        if s.project['active_job_id']:raise ApiError(409,'PROJECT_BUSY','模拟任务正在运行',True)
        status,response,schema=self.mutate(path,request,prefix)
        s.replays[key]=(encoded,status,deepcopy(response),schema)
        self.send_json(status,response,schema)

    def mutate(self,path,request,prefix):
        s=self.server;p=s.project
        if path=='/api/projects':
            # One active project by design. New mock create replaces the sandbox.
            s.project=deepcopy(EXAMPLES['create_project']['response']['project'])
            s.jobs.clear();s.polls.clear();s.versions.clear();s.replays.clear()
            return 201,{**META,'project':s.project},'ProjectResponse'
        if path==prefix+'/clips':
            if p['current_version']:raise ApiError(409,'PROJECT_LOCKED','首版生成后素材集固定；新素材请新建项目')
            if len(p['clips'])>=15:raise ApiError(422,'VALIDATION_ERROR','模拟素材上限 15 段')
            clip=deepcopy(EXAMPLES['upload_clip']['response']['clip'])
            clip.update(clip_id=f"clip_{len(p['clips'])+1:02d}",filename=request['file'])
            p['clips'].append(clip)
            return 201,{**META,'project_id':p['project_id'],'clip':clip},'ClipResponse'
        if path==prefix+'/current-version':
            self.require_base(request['base_version_id'])
            if request['version_id'] not in s.versions:raise ApiError(404,'NOT_FOUND','目标版本不存在')
            p['current_version']=deepcopy(s.versions[request['version_id']])
            p['settings']=deepcopy(p['current_version']['settings']);p['pending_selection']=None
            return 200,{**META,'project':p},'ProjectResponse'
        kind='edit' if path.endswith('/edits') else 'generate'
        if kind=='edit':self.require_base(request['base_version_id'])
        else:
            if p['current_version']:raise ApiError(409,'PROJECT_LOCKED','已有成功版本，请使用修改接口')
            if not p['clips']:raise ApiError(422,'VALIDATION_ERROR','没有素材')
        jid=f'job_{s.next_job:03d}';s.next_job+=1
        job=deepcopy(EXAMPLES['job_queued']['response']['job'])
        job.update(job_id=jid,request_id=request['request_id'],kind=kind,
                   base_version_id=request.get('base_version_id'))
        s.jobs[jid]=job;s.polls[jid]=0
        # Private mock bookkeeping; not serialized inside the Job contract.
        if not hasattr(s,'inputs'):s.inputs={}
        s.inputs[jid]=deepcopy(request)
        p['active_job_id']=jid;p['pending_selection']=None
        return 202,{**META,'project_id':p['project_id'],'job_id':jid},'JobAccepted'

    def require_base(self,base):
        current=self.server.project['current_version']
        if current is None or base!=current['version_id']:
            raise ApiError(409,'STALE_VERSION','请刷新项目并基于当前版本重试')

    def finish_job(self,job):
        s=self.server;p=s.project;request=s.inputs[job['job_id']]
        state=s.scenario
        if state in ('failed','interrupted'):
            template=EXAMPLES['job_'+state]['response']['job']
            job.update(status=state,error=deepcopy(template['error']),progress=None,message=template['message'])
        elif state=='needs_selection' and job['kind']=='edit' and request['input']['kind']=='instruction' and len(p['clips'])>=2:
            resolution={'decision':'needs_selection','prompt':'模拟：请选择素材',
                        'candidates':[{'clip_id':c['clip_id'],'label':c['filename']} for c in p['clips'][:2]]}
            job.update(status='needs_selection',resolution=resolution,progress=None,message='模拟：等待选择')
            p['pending_selection']={'job_id':job['job_id'],'base_version_id':job['base_version_id'],'resolution':deepcopy(resolution)}
        else:
            settings=deepcopy(p['settings'])
            if job['kind']=='generate':settings.update(request['settings'])
            elif request['input']['kind']=='operations':
                for op in request['input']['operations']:
                    if op['type']=='set_warmth':settings['warmth_override']=op['value']
                    elif op['type']=='set_title':settings['title_overrides'][op['field']]=op['value']
                    elif op['type']=='remove_clip':
                        if op['clip_id'] not in [c['clip_id'] for c in p['clips']]:
                            job.update(status='failed',progress=None,message='模拟：素材不存在',
                                error={'code':'VALIDATION_ERROR','message':'素材不存在','retryable':False})
                            p['active_job_id']=None
                            return
                        if op['clip_id'] not in settings['excluded_clip_ids']:settings['excluded_clip_ids'].append(op['clip_id'])
                        settings['duration_policy']={'mode':'natural','target_seconds':None,'tolerance_frames':0}
            vid=f'version_mock_{s.next_version:03d}';s.next_version+=1
            version=deepcopy(EXAMPLES['project_done']['response']['project']['current_version'])
            version.update(version_id=vid,parent_version_id=job['base_version_id'],settings=settings,
                video_url=f"/api/projects/{p['project_id']}/versions/{vid}/video",
                duration_frames=max(90,900-90*len(settings['excluded_clip_ids'])),summary='模拟结果：未调用 AI 或 FFmpeg')
            s.versions[vid]=deepcopy(version);p['current_version']=version;p['settings']=deepcopy(settings)
            job.update(status='done',version_id=vid,video_url=version['video_url'],summary=version['summary'],
                       progress=None,message='模拟：完成')
        p['active_job_id']=None

    def send_media(self,download):
        media=self.server.media
        if media is None or not media.is_file():raise ApiError(404,'FIXTURE_MEDIA_MISSING','未提供 --media 本地 MP4；当前仅能检查界面状态')
        size=media.stat().st_size;start=0;end=size-1;status=200
        requested=self.headers.get('Range')
        if requested:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            valid=match is not None and any(match.groups()) and size>0
            if valid:
                lo,hi=match.groups()
                if lo:start=int(lo);end=min(int(hi),size-1) if hi else size-1
                else:start=max(0,size-int(hi));end=size-1
                valid=0<=start<=end<size
            if not valid:
                return self.send_json(416,{**META,'error':{'code':'INVALID_RANGE','message':'范围不合法','retryable':False}},
                    'ErrorResponse',{'Content-Range':f'bytes */{size}'})
            status=206
        self.send_response(status)
        self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(max(0,end-start+1)))
        self.send_header('X-Auto-Vlog-Simulation','true')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        if download:self.send_header('Content-Disposition','attachment; filename="mock-preview.mp4"')
        self.end_headers()
        if self.command!='HEAD':
            with media.open('rb') as f:
                f.seek(start);remaining=end-start+1
                while remaining>0:
                    block=f.read(min(65536,remaining))
                    if not block:break
                    self.wfile.write(block);remaining-=len(block)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--scenario',choices=['success','failed','interrupted','needs_selection','rendering'],default='success')
    parser.add_argument('--media',type=Path)
    args=parser.parse_args()
    if args.media is not None and not args.media.is_file():parser.error('--media 文件不存在')
    server=MockServer(('127.0.0.1',args.port),args.scenario,args.media)
    print(f'MOCK ONLY: http://127.0.0.1:{server.server_port}; all results simulation=true',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
