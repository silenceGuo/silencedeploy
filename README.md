# silencedeploy 文件说明
基于python3 编写

pip安装需要运行环境安装python对应包

部署支持tomcat,jar,node等项目，分为传统模式部署和k8s模式部署

支持线程池执行多任务

config 配置文件目录

control 控制脚本目录

deployEnv模板目录

tools 公共模块目录


可以直接运行脚本执行或者通过Jenkins调用ssh脚本执行。
# 使用说明
普通tomcat部署执行sh文件授权
cd /silencedeploy

chmod +x deployEnv/normal/templates/tomcat-7.0.64/bin/*.sh

修改/silencedeploy/control/normal/deploy_agent.py 包应用路径

sys.path.append('/silencedeploy') ## 项目的绝对路径

k8s部署模式脚本位于 control/k8s/deploy_controlk8s.py

使用方式：python  deploy_controlk8s.py -n xkj-upload -a build  -p xkj -e dev -m master -v v2

支持：初始化，打包，构建 ，回滚，git仓库回滚 执行部署结果检查等。

k8s部署模式脚本位于 control/normal/deploy_control.py

使用方式：python deploy_control.py -n xkj-upload -a build  -p xkj -e dev -m master -v v2

支持：初始化，打包，构建 ，回滚，git仓库回滚 执行部署结果检查等。

