#
# generate_app_ui_test_report.py
# @description 
# @created 2021-04-13T10:59:18.000Z+08:00
# @last-modified 2023-03-27T18:20:59.510Z+08:00
#

from base.read_report_config import Read_Report_Config
from common.custom_multiprocessing import Custom_Pool
from common.dateTimeTool import DateTimeTool
from common.network import Network
from common.strTool import StrTool
import argparse
import os
import platform
import subprocess

# ===== 附件缩略图补丁：注入到生成好的 allure 报告 index.html =====
# allure 2.46 原生行为：步骤附件只显示文件名行，点击直接弹全屏查看器按原始尺寸渲染
# （手机长图半屏只能看到一条）。此补丁实现：附件行内默认显示小缩略图（图片/视频），
# 点击缩略图走 allure 原生查看器放大/播放；查看器媒体自适应窗口高度，不再无限拉长。
APPUI_PATCH_MARKER = '<!-- appui-attachment-thumbnail-patch -->'
APPUI_PATCH_STYLE = """
<style>
.attachment-row{flex-wrap:wrap;}
.appui-thumb-holder{flex-basis:100%;width:100%;padding:2px 12px 8px 40px;box-sizing:border-box;}
.appui-thumb{display:block;max-width:100px;max-height:60px;width:auto;height:auto;border-radius:6px;
  border:1px solid rgba(127,127,127,.45);cursor:zoom-in;object-fit:cover;background:rgba(127,127,127,.12);}
.appui-thumb--video{width:100px;height:56px;background:#000;}
.modal__window{max-height:calc(100vh - 48px) !important;overflow:auto !important;}
.modal__content{overflow:auto !important;}
.modal__window .attachment-preview__media{max-width:100% !important;max-height:calc(100vh - 160px) !important;
  width:auto !important;height:auto !important;object-fit:contain !important;}
</style>
"""
APPUI_PATCH_SCRIPT = """
<script>
(function(){
  var EXT={'image/png':'.png','image/jpeg':'.jpg','image/jpg':'.jpg','image/gif':'.gif','image/webp':'.webp',
           'image/bmp':'.bmp','video/mp4':'.mp4','video/webm':'.webm','video/quicktime':'.mov'};
  function openFullscreen(row){
    var btn=row.querySelector('.attachment-row__fullscreen');
    if(btn){btn.click();return;}
    var link=row.querySelector('.attachment-row__name');
    if(link){link.click();}
  }
  function decorate(row){
    if(row.querySelector('.appui-thumb')){return;}
    var type=row.getAttribute('data-type')||'';
    var uid=row.getAttribute('data-uid')||'';
    var ext=EXT[type];
    if(!ext||!uid){return;}
    var url='data/attachments/'+uid+ext;
    var el;
    if(type.indexOf('video/')===0){
      el=document.createElement('video');
      el.className='appui-thumb appui-thumb--video';
      el.muted=true;el.preload='metadata';el.playsInline=true;
    }else{
      el=document.createElement('img');
      el.className='appui-thumb';
      el.loading='lazy';
    }
    el.src=url;
    el.addEventListener('click',function(ev){ev.stopPropagation();openFullscreen(row);});
    var holder=document.createElement('div');
    holder.className='appui-thumb-holder';
    holder.appendChild(el);
    row.appendChild(holder);
  }
  function scan(){
    var rows=document.querySelectorAll('.attachment-row');
    for(var i=0;i<rows.length;i++){decorate(rows[i]);}
  }
  function start(){
    scan();
    new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});
  }
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',start);}
  else{start();}
})();
</script>
"""

def inject_attachment_thumbnail_patch(report_index_dir):
    """向 allure 报告 index.html 注入附件缩略图样式与脚本（幂等，已注入则跳过）。"""
    index_file = os.path.join(report_index_dir, 'index.html')
    if not os.path.isfile(index_file):
        print('%s未找到报告index.html，跳过缩略图补丁: %s' % (DateTimeTool.getNowTime(), index_file))
        return
    with open(index_file, 'r', encoding='utf-8') as f:
        html = f.read()
    if APPUI_PATCH_MARKER in html:
        return
    html = html.replace('</head>', APPUI_PATCH_MARKER + APPUI_PATCH_STYLE + '</head>', 1)
    html = html.replace('</body>', APPUI_PATCH_SCRIPT + '</body>', 1)
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print('%s已注入附件缩略图补丁: %s' % (DateTimeTool.getNowTime(), index_file))


def generate_windows_reports(report_dir,test_time,port):
    generate_report_command='allure generate %s/report_data -o %s/report/app_ui_report_%s'%(report_dir,report_dir,test_time)
    subprocess.check_output(generate_report_command,shell=True)
    inject_attachment_thumbnail_patch('%s/report/app_ui_report_%s'%(report_dir,test_time))
    open_report_command='start cmd.exe @cmd /c "allure open -p %s %s/report/app_ui_report_%s"'%(port,report_dir,test_time)
    subprocess.check_output(open_report_command,shell=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('-sp', '--start_port', help='生成报告使用的开始端口，多份报告每次加1', type=str)
    args=parser.parse_args()
    if args.start_port:
        start_port=args.start_port
    else:
        report_config = Read_Report_Config().report_config
        start_port = report_config.app_ui_start_port
    test_time=DateTimeTool.getNowTime('%Y_%m_%d_%H_%M_%S_%f')
    report_dirs = []
    devices_dirs = os.listdir('output/app_ui/')
    for device_dir in devices_dirs:
        for report_dir in os.listdir('output/app_ui/' + device_dir):
            report_dirs.append('output/app_ui/' + device_dir + '/' + report_dir)

    if 'Windows' == platform.system():
        # 初始化进程池
        p_pool = Custom_Pool(20)
        for i in range(len(report_dirs)):
            port = str(int(start_port) + i)
            get_allure_process_id_command = 'netstat -ano|findstr "0.0.0.0:%s"' % port
            try:
                get_allure_process_id = subprocess.check_output(get_allure_process_id_command, shell=True)
                get_allure_process_id = get_allure_process_id.decode('utf-8')
                get_allure_process_id = StrTool.getStringWithLBRB(get_allure_process_id, 'LISTENING', '\r\n').strip()
                kill_allure_process_command = 'taskkill /F /pid %s' % get_allure_process_id
                try:
                    subprocess.check_call(kill_allure_process_command, shell=True)
                except:
                    print('%s关闭allure进程,进程id:%s,该进程监听已监听端口:%s'%(DateTimeTool.getNowTime(),get_allure_process_id,port))
            except:
                print('%sallure未查找到监听端口%s的服务' %(DateTimeTool.getNowTime(),port))
            print('%s生成报告%s/report/app_ui_report_%s,使用端口%s'%(DateTimeTool.getNowTime(),report_dirs[i],test_time,port))
            print('%s报告地址:http://%s:%s/' % (DateTimeTool.getNowTime(),Network.get_local_ip(), port))
            p = p_pool.apply_async(generate_windows_reports, (report_dirs[i],test_time,port))
        p_pool.close()
        p_pool.join()
    else:
        # 获得当前allure所有进程id
        get_allure_process_ids_command = "ps -ef|grep -i allure\\.CommandLine|grep -v grep|awk '{print $2}'"
        allure_process_ids = subprocess.check_output(get_allure_process_ids_command, shell=True)
        allure_process_ids = allure_process_ids.decode('utf-8')
        allure_process_ids = allure_process_ids.split('\n')

        for i in range(len(report_dirs)):
            port = str(int(start_port) + i)
            # 获得当前监听port端口的进程id：macOS 用 lsof（netstat 无 -p 选项），Linux 用 netstat -anp
            if 'Darwin' == platform.system():
                get_port_process_ids_command = "lsof -ti tcp:%s 2>/dev/null" % port
            else:
                get_port_process_ids_command = "netstat -anp 2>/dev/null|grep -i " + port + "|grep -v grep|awk '{print $7}'|awk -F '/' '{print $1}'"
            try:
                port_process_ids = subprocess.check_output(get_port_process_ids_command, shell=True)
                port_process_ids = port_process_ids.decode('utf-8')
                port_process_ids = port_process_ids.split('\n')
            except subprocess.CalledProcessError:
                port_process_ids = []
            is_find = False
            for port_process_id in port_process_ids:
                if is_find:
                    break
                for allure_process_id in allure_process_ids:
                    allure_process_id = allure_process_id.strip()
                    port_process_id = port_process_id.strip()
                    if allure_process_id == port_process_id and not is_find and allure_process_id and port_process_id:
                        print('%s关闭allure进程,进程id:%s,该进程监听已监听端口:%s'%(DateTimeTool.getNowTime(),allure_process_id.strip(),port))
                        subprocess.check_output("kill -9 " + allure_process_id.strip(), shell=True)
                        is_find = True
                        break
            print('%s生成报告%s/report/app_ui_report_%s,使用端口%s'%(DateTimeTool.getNowTime(),report_dirs[i],test_time,port))
            print('%s报告地址:http://%s:%s/' % (DateTimeTool.getNowTime(),Network.get_local_ip(), port))
            generate_report_command='allure generate %s/report_data -o %s/report/app_ui_report_%s'%(report_dirs[i],report_dirs[i],test_time)
            subprocess.check_output(generate_report_command,shell=True)
            inject_attachment_thumbnail_patch('%s/report/app_ui_report_%s'%(report_dirs[i],test_time))
            open_report_command='nohup allure open -p %s %s/report/app_ui_report_%s >logs/generate_app_ui_test_report_%s.log 2>&1 &'%(port,report_dirs[i],test_time,test_time)
            subprocess.check_output(open_report_command,shell=True)