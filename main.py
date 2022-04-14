#!/usr/bin/deploytEnv python
# -*- coding: utf-8 -*- 
# @Time : 2022-4-14 上午 9:00 
# @Author : damon.guo 
# @File : main.py 
# @Software: PyCharm
# from common import git_
# import tools.git_control
from tools.git_control import git
from tools.build_control import build
# from tools import *
# from tools.git
# from build_control import build
# import common
from tools.common import *
from control.k8s.deploy_controlk8s import k8s
def parallel():
    options, args = getOptions()
    serverName = options.serverName
    projectName = options.projectName
    envName = options.envName
    action = options.action
    envConf = "/silencedeploy/config/config.yaml"
    confDict = readYml(envConf)
    if projectName == "node":
        serverConf = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
    elif projectName == "springcloud":
        serverConf = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
    elif projectName == "xkj":
        serverConf = "/silencedeploy/config/startService-{envName}.yaml".format(envName=envName)
        # serverConf = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
        gitsysConfig = confDict["gitsys"]["gitsysConfig"]
        gitsysConfigDir = confDict["gitsys"]["gitsysConfigDir"]

        if not os.path.exists(gitsysConfigDir):
            Gitinit("sysconfig", gitsysConfig, gitsysConfigDir)
        # sys.exit(1)
    else:
        myloger(name=serverName, msg="类型错误:%s" % projectName)
        sys.exit()
    serverDict = readYml(serverConf)
    # print(serverDict)
    startConf = confDict["startServer"].format(envName=envName, projectName=projectName)
    deploythreadNum = confDict["deploythreadNum"]
    buildthreadNum = confDict["buildthreadNum"]
    kubeconfig = confDict["kubeconfig"].format(envName=envName)
    kubectl = confDict["kubectl"]
    resultYml = confDict["resultYml"].format(envName=envName)
    if action == "reset":
        # 因错误的执行或者强制停止可以重置启动文件，控制从第一个工程执行操作
        cleanfile(startConf)
        myloger(name="consle", msg="情况启动文件顺序:%s" % startConf)
        sys.exit()
    # threadPool = ThreadPoolExecutor(max_workers=threadNum, thread_name_prefix="test_")
    if serverName == "all":
        sortlist = sortedServerName(serverDict)
        tpool=[]
        # if action in ["deploy","status", "build", "restart", "redeploy", "canary", "rollback"]:
        if action in ["deploy", "redeploy","restart", "canary", "rollback","status"]:
            for serName in sortlist:
                if serName == "all":
                    continue
                if not serverDict[serName]["Parallel"]:
                    myloger(name=serName, msg="单线程执行:%s" % serName)
                    maink8s(serName, serverConf, envConf)
                else:
                    # common.myloger(name=serName, msg="多线程执行:%s，并发线程数:%s" % (serName, threadNum))
                    # obj = threadPool.submit(main, serName, serverConf, envConf)
                    tpool.append(serName)
            # for future in as_completed(tpool):
            #     data = future.result()
            #     common.myloger(name=name, msg="线程执行完成!")
            # threadPool.shutdown(wait=True)

            threadPool(tpool, deploythreadNum, maink8s, serverConf, envConf)
            # common.showResult(resultYml, action, serverName)
            # common.myloger(name=name, msg="线程执行完成!")
            # common.myloger(name=serName, msg="执行完成:%s" % serName)
        elif action in ["build","rebuild"]:
            # common.threadPool2(sortlist, threadNum, main, [serverConf], [envConf])
            threadPool(sortlist, buildthreadNum, maink8s, serverConf, envConf)

        else:
            if readfile(startConf):
                serName, point = readfile(startConf)
            else:
                point = 0
            for serName in sortlist[int(point):]:
                if serName == "all":
                    continue
                ser_index = sortlist.index(serName)
                info = "%s:%s" % (ser_index, serName)
                writhfile(startConf, info)
                maink8s(serName, serverConf, envConf)
                myloger(name=serName, msg="等待2s")
                time.sleep(2)
        if action == "build" or action == "deploy":
            showResult(resultYml, action, serverName)
        cleanfile(startConf)
    else:
        if serverName not in serverDict:
            myloger(name=serverName, msg="%s:服务名错误" % serverName)
            printServerName(serverDict)
            sys.exit()
        maink8s(serverName, serverConf, envConf)
        if action == "build" or action == "deploy":
            showResult(resultYml, action, serverName)
        cleanfile(startConf)
def maink8s(serverName,serverConf,envConf):
    # options = Options()
    options, args = getOptions()
    options.serverName = serverName
    k = k8s(serverConf, envConf, serverName)
    k.build.serverName = serverName
    k.build.buildDir = k.build.serverDict[k.build.serverName]["buildDir"].format(envName=k.build.envName)
    k.build.masterDir = k.build.serverDict[k.build.serverName][k.build.codeType]["masterDir"].format(envName=k.build.envName)
    if k.buildType == "node":
         k.build.nodeversion = k.build.serverDict[k.build.serverName]["nodeversion"]
    k.build.deployFile = k.build.serverDict[k.build.serverName]["deployFile"].format(envName=k.build.envName)
    k.build.Port = k.build.serverDict[k.build.serverName]["Port"]
    k.build.repUrl = k.build.confDict["imageRepo-{envName}".format(envName=k.build.envName)]["url"]
    k.build.nameSpace = k.build.confDict["imageRepo-{envName}".format(envName=k.build.envName)]["nameSpace"]
    k.build.userName = k.build.confDict["imageRepo-{envName}".format(envName=k.build.envName)]["userName"]
    k.build.passWord = k.build.confDict["imageRepo-{envName}".format(envName=k.build.envName)]["passWord"]
    k.build.replicas = k.build.serverDict[k.build.serverName]["replicas"]
    # k.git.masterDir = k.build.serverDict[k.build.serverName]["gitRepo"]["masterDir"].format(envName=k.build.envName)
    if k.codeType == "git":
         k.git.serverName = serverName
    if k.build.action == "build":
        # 构建镜像推送镜像
        if not k.build.mbranchName:
            common.myloger(name=k.build.serverName, msg="follow -m branchName")
            return False
        if k.buildType == "node":
            if k.build.buildNode():
                if k.build.buildImageNode():
                    k.build.pushImage()
        elif k.buildType == "tomcat":
            if k.build.buildMaven():
                k.build.buildMavenTomcat()
                k.build.buildImageTomcat()
                k.build.pushImage()
        else:## jar
          if k.build.buildMaven():
              if k.build.buildImage():
                    k.build.pushImage()
    elif k.build.action == "buildMaven":
        if k.buildType == "tomcat":
            if k.build.buildMaven():
                # pass
               k.build.buildMavenTomcat()
               if k.build.buildImageTomcat():
                   k.build.pushImage()
        elif k.buildType == "jar":
            if k.build.buildMaven():
                if k.build.buildImage():
                    k.build.pushImage()
        else:
            pass
    elif k.build.action == "sonar":
        common.sonar(k.build.serverName,k.mvn,k.build.masterDir)
    elif k.build.action == "deploy2":
        # if k.mbranchName and k.branchName != "master":
        #     k.git.merge(k.branchName, k.mbranchName)
        #
        if k.build.buildType == "node":
            if k.build.buildNode():
                if k.build.buildImageNode():
                    k.build.pushImage()
        elif k.build.buildType == "tomcat":
            if k.build.buildMaven():
                k.build.buildMavenTomcat()
                if k.build.buildImageTomcat():
                    k.build.pushImage()
        else:
            if k.build.buildMaven():
                if k.build.buildImage():
                    k.build.pushImage()
        k.delpoyK8S()
        # k.reDeploy()
    elif k.build.action == "deploy":
        k.delpoyK8S()
    elif k.build.action == "redeploy":
        k.delpoyK8S()
    elif k.build.action == "restart":
        k.reDeploy()
    elif k.build.action == "canary":
        # if k.mbranchName and k.branchName != "master":
        #     k.git.merge(k.branchName, k.mbranchName)
        if k.buildType == "node":
            if k.build.buildImageNode():
                k.build.pushImage()
        else:
            if k.build.buildMaven():
                k.build.buildImage()
                k.build.pushImage()
        k.canary()
    elif k.build.action == "merge":
        # 合并分支
        if k.build.mbranchName and k.build.branchName != "master":
            k.git.merge(k.build.branchName, k.mbranchName)
            return True
        k.git.myloger(name=k.build.serverName, msg="follow -b branchName -m mBrancherName")
    elif k.build.action == "init":
        # git仓库本地初始化
        k.git.init()
        # k.git.init(k.serverName)
    elif k.build.action == "reinit":
        # git仓库本地重新初始化
         k.git.reinit()
    elif k.build.action == "rollback":
        # git仓库本地重新初始化
        k.rollback()
    elif k.build.action == "createBranch":
        # 创建新分支
        if k.build.branchName:
            if k.git.deleteBranch(k.build.mbranchName, k.build.branchName):
                k.git.createBranch(k.build.mbranchName, k.build.branchName)
    elif k.build.action == "revert":
        k.git.revert(k.build.mbranchName, k.build.versionId)
    elif k.build.action == "getCommit":
        k.git.getCommitList(k.build.mbranchName)
    elif k.build.action == "status":
        # 获取deployment 部署状态
        k.getStatus()
        k.getHistoryVersion()
    else:
        myloger(name=k.build.serverName, msg="follow -n serverName -a action[build,deploy,rollback,status,init,reinit,merge]"
                                             " -b branchName -m mBranch"
                                             " -e envName -v versionId1")
        return False

def main():
    # parallel()
    envConf = "/silencedeploy/config/config.yaml"
    # confDict = readYml(envConf)
    serverConf = "/silencedeploy/config/startService.yaml"
    k = k8s(serverConf, envConf, "xkj-upload")
    k.init()
    print(k.build.confDict)

if __name__ == "__main__":
    envConf = "/silencedeploy/config/config.yaml"
    # confDict = readYml(envConf)
    serverConf = "/silencedeploy/config/startService.yaml"
    # options, args = getOptions()
    # serverName = options.serverName
    # projectName = options.projectName
    # envName = options.envName
    # action = options.action
    # maink8s(serverName,serverConf,envConf)
    parallel()
    # dicttmp ={}
    # xmx = 123
    # dicttmp["xms"] = 123
    # dicttmp["xmx"] = 324
    # # xmn = str(int(xmx/2 * (3.0 / 8)))
    # xmn = str(int(xmx / 2))
    # dicttmp["xmn"] = xmn
    # # 应用skywalking 增加环境名称
    # dicttmp["pinpointid"] = "sd"
    # dicttmp["xmx"]
    # genTmpFile("xkj-upload-", dicttmp, "/python_yek/xkj-k8s/templates/catalina.sh.tmp2", "/home/project/k8s-build-git/xkj-upload-dev/catalina.sh")
