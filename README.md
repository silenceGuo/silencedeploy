# silencedeploy
部署支持tomcat,jar,node等项目，分为传统模式部署，和k8s模式部署
支持线程池执行多任务
可以直接运行脚本执行或者通过Jenkins调用ssh脚本执行。

k8s部署模式脚本位于 control/k8s/deploy_controlk8s.py
使用方式：python  deploy_controlk8s.py -n xkj-upload -a build  -p xkj -e dev -m master -v v2
支持：初始化，打包，构建 ，回滚，git仓库回滚 执行部署结果检查等。

k8s部署模式脚本位于 control/normal/deploy_controlv2.py
使用方式：
python deploy_controlv2.py -n xkj-upload -a build  -p xkj -e dev -m master -v v2
支持：初始化，打包，构建 ，回滚，git仓库回滚 执行部署结果检查等。

