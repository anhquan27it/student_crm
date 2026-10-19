import http from 'node:http';
import https from 'node:https';
import { readFile, stat } from 'node:fs/promises';
import { resolve, extname, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), 'public');
const port = Number(process.env.PORT || 5173);
const host = process.env.HOST || '127.0.0.1';
const upstream = new URL(process.env.FRAPPE_URL || 'http://127.0.0.1:8000');
const site = process.env.FRAPPE_SITE || 'studentcrm.local';
const mime = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.json':'application/json; charset=utf-8'};
const allowed = /^(?:login|logout|student_crm\.(?:api\.(?:get_session_roster|submit_bulk_attendance|get_advisor_dashboard)|experience\.(?:get_terms|get_workbench|unread_count)|support\.(?:list_cases|get_case|update_case|assignment_history|assign_advisor|list_my_attendance|request_correction|list_corrections|get_correction|review_correction|list_notifications|get_notification|mark_notification_read|get_support_dashboard|get_data_quality)|portal\.(?:get_context|get_overview|list_offerings|list_sessions|list_students|list_interventions|get_student_detail|get_warning_detail|save_intervention|update_warning|get_settings|save_settings|get_catalog|save_record|link_options)))$/;
const security = {'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"};

export function isAllowedMethod(pathname) {
  return pathname.startsWith('/api/method/') && allowed.test(pathname.slice('/api/method/'.length));
}

export const server = http.createServer(async (req, res) => {
  for (const [k,v] of Object.entries(security)) res.setHeader(k,v);
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    if (url.pathname.startsWith('/api/')) {
      if (!isAllowedMethod(url.pathname) || !['GET','POST'].includes(req.method)) {
        res.writeHead(404, {'Content-Type':'application/json'});res.end(JSON.stringify({message:'Endpoint not available.'}));return;
      }
      if (req.method === 'POST' && req.headers.origin && req.headers.origin !== `http://${req.headers.host}` && req.headers.origin !== `https://${req.headers.host}`) {
        res.writeHead(403,{'Content-Type':'application/json'});res.end(JSON.stringify({message:'Origin not allowed.'}));return;
      }
      if (Number(req.headers['content-length'] || 0)>1_100_000) {res.writeHead(413);res.end();return;}
      const headers={host:site,accept:'application/json','accept-encoding':'identity'};
      for (const key of ['cookie','content-type','content-length','x-frappe-csrf-token']) if(req.headers[key]) headers[key]=req.headers[key];
      const transport=upstream.protocol==='https:'?https:http;
      const proxy=transport.request(new URL(url.pathname+url.search,upstream),{method:req.method,headers,timeout:30000}, response=>{
        for (const key of ['content-type','set-cookie']) if(response.headers[key]) res.setHeader(key,response.headers[key]);
        const cookies=response.headers['set-cookie'];
        if(cookies) res.setHeader('set-cookie',cookies.map(cookie=>cookie.replace(/;\s*Domain=[^;]+/ig,'')));
        res.setHeader('Cache-Control','no-store');res.statusCode=response.statusCode;response.pipe(res);
      });
      proxy.on('timeout',()=>proxy.destroy(new Error('Upstream timeout')));
      proxy.on('error',()=>{if(res.writableEnded)return;if(!res.headersSent)res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({message:'Không kết nối được Frappe. Kiểm tra Ubuntu WSL và bench start.'}));});
      let received=0;
      req.on('data',chunk=>{received+=chunk.length;if(received>1_100_000){proxy.destroy();if(!res.headersSent)res.writeHead(413);res.end();}});
      req.pipe(proxy);return;
    }
    if (!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
    let target=resolve(root,'.'+decodeURIComponent(url.pathname));
    if(target!==root&&!target.startsWith(root+sep)){res.writeHead(403);res.end();return;}
    if(url.pathname==='/' || !extname(target))target=resolve(root,'index.html');
    const info=await stat(target);if(!info.isFile())throw new Error('Missing');
    res.setHeader('Content-Type',mime[extname(target)]||'application/octet-stream');res.setHeader('Cache-Control','no-cache');
    res.end(req.method==='HEAD'?undefined:await readFile(target));
  } catch {if(!res.headersSent)res.writeHead(404);res.end('Not found');}
});
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))server.listen(port,host,()=>console.log(`Student CRM: http://${host}:${port}\nFrappe: ${upstream.origin} (${site})`));
