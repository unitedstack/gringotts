# -*- coding: utf-8 -*-

import json
import requests
import time

#subject = u"[UnitedStack]11月好文推荐"
#content = u"""
#    <div style="margin:auto;width:700px;padding:20px;font-size:12px;font-family:Lucida Grande,Lucida Sans,Lucida Sans Unicode,Arial,Helvetica,Verdana,sans-serif;">
#      <div style="height:60px;border-bottom:1px solid #bfbfbf;">
#        <img src="http://ustackemail.qiniudn.com/email_logo.png" style="width:181px;height:36px;margin-top:12px;"/>
#      </div>
#      <div>
#        <div style="font-size:25px;color:#000;padding:30px 0px;">Special Savings, From UnitedStack.</div>
#        <img src="http://ustackemail.qiniudn.com/1.png" style="width:700px;">
#      </div>
#      <div style="margin-top:66px;border-top:1px solid #bfbfbf;">
#        <div style="font-size:25px;color:#000;padding:30px 0px 25px 0px;">11月的一场OpenStack SDN 深度讨论会</div>
#        <div style="font-size:17px;line-height:25px;padding-bottom:12px;">UnitedStack 主办的关于OpenStack的技术讨论会第一场《OpenStack云服务SDN解决方案研讨会》已经圆满结束，欢迎关注官方微博和Meetup了解下一次技术讨论会。</div>
#        <img src="http://ustackemail.qiniudn.com/3.png" style="width:700px;">
#        <div style="font-size:17px;line-height:25px;padding-top:16px;">想了解作为OpenStack云中原生的SDN控制器Neutron与OpenContrail、OpenFlow-based SDN方案等的异同及Neutron可能的优化方式？</div>
#        <a href="https://www.ustack.com/news/nov-openstack-sdn/" target="_blank" style="width:250px;height:36px;line-height:36px;display:block;text-align:center;color:#fff;font-size:17px;background-color:#e67a19;border-radius:3px;text-decoration:none;margin:44px auto;">更多</a>
#      </div>
#      <div style="margin-top:66px;border-top:1px solid #bfbfbf;">
#        <div style="font-size:25px;color:#000;padding:30px 0px 25px 0px;">程辉：OpenStack生态圈分析</div>
#        <div style="font-size:17px;line-height:25px;padding-bottom:12px;">OpenStack开源项目背后有哪些商业公司？各家公司的产品、服务和商业模式如何？哪家公司最赚钱？OpenStack当前发展到了哪个阶段？了解这些问题，邀您仔细阅读程辉先生的最新长作《OpenStack商业生态圈分析》</div>
#        <img src="http://ustackemail.qiniudn.com/2.png" style="width:700px;">
#        <a href="https://www.ustack.com/blog/openstack-business-ecosystem/" target="_blank" style="width:250px;height:36px;line-height:36px;display:block;text-align:center;color:#fff;font-size:17px;background-color:#e67a19;border-radius:3px;text-decoration:none;margin:44px auto;">更多</a>
#      </div>
#      <div style="margin-top:66px;border-top:1px solid #bfbfbf;position:relative;font-size:17px;padding-top:30px;height:105px;">
#        <div style="width:500px;float:left;">
#          <div style="height:26px;">了解更多OpenStack动态咨询&阅读更多技术文章，请关注：</div>
#          <div style="height:26px;">UnitedStack官方微信：UStack1(此处加微信二维码）</div>
#          <div style="height:26px;">UnitedStack官方微博：UnitedStack</div>
#          <div style="height:26px;">UnitedStack技术精品库：<a style="color:#e67a19;text-decoration:none;" target="_blank" href="http://www.ustack.com/blog">www.ustack.com/blog</a></div>
#        </div>
#        <img style="float:right;display:block;width:97px;height:97px;" src="http://ustackemail.qiniudn.com/qr.png"></img>
#      </div>
#      <div style="border-top:1px solid #bfbfbf;margin-top:20px;height:60px;text-align:center;font-size:17px;line-height:60px;"><a href="http://www.ustack.com" target="_blank" style="color:#000;text-decoration:none;">www.ustack.com</a></div>
#    </div>
#"""

subject = u"[UnitedStack] 北京1区 12月14日中午 网络故障报告"
content = u"""
<div style="padding-top:0px;padding-bottom:0px;font-size:12px;background-color:#f1f1f1;font-family:Lucida Grande,Lucida Sans,Lucida Sans Unicode,Arial,Helvetica,Verdana,sans-serif;">
<div style="margin:auto;max-width:800px;">
<div style="height:60px;background-color:#00b1c8;border-top-left-radius:5px;border-top-right-radius:5px;"><img src="http://ustackemail.qiniudn.com/logo.png" style="width:183px;height:36px;margin-top:11px;margin-left:33px;" /></div>
<div style="min-height:155px;background-color:#fff;border-bottom-left-radius:5px;border-bottom-right-radius:5px;color:#142728;padding:25px 30px;font-size:14px;line-height:20px;">
<div style="maring-bottom:10px;">尊敬的UnitedStack用户，</div>

<pre style="white-space: pre-wrap;">
您好！

因局方机房网络故障，北京1区的北京地区联通线路中断，UStack官网及用户网络服务均受影响，而移动、电信线路和省外线路则一切正常。
由于此为局方未知故障，目前已紧急切换至备用线路，我们将密切关注之后故障处理过程。造成贵方不便，我方表示深深的歉意。

故障时间：2014年12月14日 10:47 - 11:46
影响范围：北京1区 对北京地区的联通线路，移动/电信线路和省外线路不受影响。
影响业务：控制台不可用，北京1区用户网络部分中断。使用备用线路期间有可能导致延时增大。
故障原因：疑似物理光缆中断，具体原因需要等局方官方报告。

感谢您对UStack云平台的长期理解与支持！
 
UnitedStack（北京）科技有限公司
2014年12月14日
</pre>

</div>
<div style="margin:auto;text-align:center;width:100%;background-color:#fff;color:#9e9e9e;padding-top:16px;padding-bottom:16px;font-size:12px;"><a href="http://www.ustack.com" style="color:#9e9e9e;text-decoration:none;">UnitedStack Inc. - www.ustack.com</a></div>
</div>
</div>
"""


url="https://sendcloud.sohu.com/webapi/mail.send.xml"
params = {"use_maillist": "true",
          "api_user": "postmaster@unitedstack-push.sendcloud.org",
          "api_key": "7CVvlTcXvVDgMo8U",
          "from": "notice@mail.unitedstack.com",
          "fromname": "UnitedStack",
          #"to": "all_users@maillist.sendcloud.org",
          #"to": "active_users@maillist.sendcloud.org",
          "to": "active_users_in_lg@maillist.sendcloud.org",
          #"to": "test@maillist.sendcloud.org",
          "subject": subject,
          "html": content.encode('utf-8')}

r = requests.post(url, data=params)
print r.text
