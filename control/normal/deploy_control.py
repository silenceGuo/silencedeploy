#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 2022-4-15 上午 10:59 
# @Author : damon.guo 
# @File : deploy_controlv2.py 
# @Software: PyCharm
from tools.git_control import git
from tools.build_control import build
from tools.common import *

class deployControl():
    def __init__(self,serverConf,envConf,serverName):
        self.build = build(serverConf, envConf, serverName)
        self.codeType = self.build.serverDict[serverName]["codeType"]
        self.buildType = self.build.serverDict[serverName]["buildType"]
        # self.sysConfigDir = self.build.confDict["gitsys"]["gitsysConfigDir"]
        # self.gitsysConfig = self.build.confDict["gitsys"]["gitsysConfig"]
        if self.codeType == "git":
            self.git = git(serverConf, serverName)
        else:
            pass
        self.tmpOutDir = self.build.confDict["tmpOutDir"]
        if not os.path.exists(self.tmpOutDir):
            os.makedirs(self.tmpOutDir)
        self.mvn = self.build.confDict["mvnPath"]
        self.python = self.build.confDict["pythonPath"]
        self.ansibleHost = self.build.confDict["ansibileHost"]
        self.remotePy = self.build.confDict["remotePy"]
        self.deploymentAppDir = self.build.confDict["deploymentAppDir"]
        self.tomcatPrefix = self.build.confDict["tomcatPrefix"]
        self.bakDir = self.build.confDict["bakDir"]
    # def initSys(self):
    #     # 初始化 syconfig本地git仓库
    #     self.git.init("sysconfig",self.sysConfigDir,self.gitsysConfig)
    # def reinitSys(self):
    #     cleanDir(self.sysConfigDir)
    #     self.git.init("sysconfig",self.sysConfigDir,self.gitsysConfig)
    def delployNodeDir(self,serverName, env):
        serverNameDict = self.build.serverDict[serverName]
        deployDir = serverNameDict["deployDir"]
        buildDir = serverNameDict["buildDir"].format(envName=env)
        distDir = os.path.join(buildDir, 'dist/')
        if env == "dev":
            deploynode = serverNameDict["devNodeName"][0]
        if env == "test":
            deploynode = serverNameDict["testNodeName"][0]
        if env == "pro":
            deploynode = serverNameDict["proNodeName"][0]

        # copyFILE = "ansible %s -i %s -m synchronize -a 'src=%s dest=%s delete=yes'" % (deploynode, ansibleHost, buildDir, deployDir)
        # 同步编译后的dist目录
        # copyFILE = "ansible %s -i %s -m synchronize -a 'src=%s dest=%s delete=yes'" % (
        # deploynode, self.ansibleHost, distDir, deployDir)
        # 本地测试用
        copyFILE = 'ansible %s -i %s -m copy -a "src=%s dest=%s"' % (
            deploynode, self.ansibleHost, distDir, deployDir)
        # ReturnExec(copyFILE)
        stdout, stderr = execSh(serverName, copyFILE)

    def execAnsible(self,serverName, deploynode, action, env, typeName, version="-1"):
        serverNameDict = self.build.serverDict[serverName]
        statusDict = {}
        myloger(name=serverName, level="INFO", msg=" server:%s is %s now " % (serverName, action))
        cmd = "ansible %s -i %s -m shell -a '%s %s -a %s -n %s -e %s -t %s -v %s'" % (
            deploynode, self.ansibleHost, self.python, self.remotePy, action, serverName, env, typeName, version)
        if action == "start":
            stdout, stderr = execSh(serverName,cmd)
        else:
            stdout, stderr = execSh(serverName,cmd)
        if "FAILED" in stdout:
            myloger(serverName, level="ERROR", msg="%s %s False on %s " % (serverName, action, env))
            return False
        elif "FAILED" in stderr:
            myloger(serverName, level="ERROR", msg="%s %s False on %s " % (serverName, action, env))
            return False
        elif "stoped" in stdout:
            statusDict[serverName] = {deploynode: "stop"}
            return statusDict
        elif "started" in stdout:
            statusDict[serverName] = {deploynode: "started"}
            return statusDict
        else:
            myloger(serverName, level="INFO", msg="%s %s True on %s " % (serverName, action, env))
            return True

    def getDeploymentTomcatPath(self,serverName):
        # deployServerDir = os.path.join(self.deploymentAppDir, "%s%s") % (self.tomcatPrefix, serverName)
        deployServerDir = self.build.serverDict[serverName]["deployDir"]
        deployServerWarDir = os.path.join(self.deploymentAppDir, "%s%s/%s") % (self.tomcatPrefix, serverName, "webapps/ROOT")
        deployServerWar = os.path.join(self.deploymentAppDir, "%s%s/%s") % (self.tomcatPrefix, serverName, "webapps/ROOT.war")
        deployServerTomcatDir = os.path.join(self.deploymentAppDir, "%s%s") % (self.tomcatPrefix, serverName)
        deployServerXmlDir = os.path.join(self.deploymentAppDir, "%s%s/%s") % (self.tomcatPrefix, serverName, "conf/server.xml")
        bakServerDir = os.path.join(self.bakDir, "%s%s") % (self.tomcatPrefix, serverName)
        return {"deployServerDir": deployServerDir,
                "deployServerWarDir": deployServerWarDir,
                "deployServerTomcatDir": deployServerTomcatDir,
                "deployServerXmlDir": deployServerXmlDir,
                "bakServerDir": bakServerDir,
                "deployServerWar": deployServerWar
                }
    def sendToNode(self,serverName, deploynode, typeName):
        # print "发送文件至远程节点 "
        myloger(serverName, level="INFO", msg="发送文件至远程节点 ")
        serverDict = self.getDeploymentTomcatPath(serverName)
        serverNameDict = self.build.serverDict[serverName]
        if typeName == "jar":
            # 为在发布前提前打包 发送到目标服务器，jar名称不能一样
            deployServerWar = os.path.join(serverNameDict["deployDir"], "ROOT.jar")
        else:
            deployServerWar = serverDict["deployServerWar"]
        deployFile = serverNameDict["deployFile"].format(envName=self.build.envName)
        copyFILE = 'ansible %s -i %s -m copy -a "src=%s dest=%s owner=tomcat group=tomcat"' % (
        deploynode, self.ansibleHost, deployFile, deployServerWar)
        execSh(serverName,copyFILE)

def main(serverName,serverConf,envConf):
    # options = Options()
    options, args = getOptions()
    options.serverName = serverName
    k = deployControl(serverConf, envConf, serverName)
    k.build.serverName = serverName
    k.build.buildDir = k.build.serverDict[k.build.serverName]["buildDir"].format(envName=k.build.envName)
    k.build.masterDir = k.build.serverDict[k.build.serverName][k.build.codeType]["masterDir"].format(envName=k.build.envName)
    if k.buildType == "node":
         k.build.nodeversion = k.build.serverDict[k.build.serverName]["nodeversion"]
    k.build.deployFile = k.build.serverDict[k.build.serverName]["deployFile"].format(envName=k.build.envName)
    k.build.http_port = k.build.serverDict[k.build.serverName]["http_port"]
    deploynode = k.build.serverDict[k.build.serverName]["{envName}NodeName".format(envName=k.build.envName)][0]
    if k.codeType == "git":
         k.git.serverName = serverName
         k.build.gitUrl = k.build.serverDict[k.build.serverName][k.build.codeType]["gitUrl"]
    if k.build.action == "build":
        # 构建镜像推送镜像
        if not k.build.mbranchName:
            myloger(name=k.build.serverName, msg="follow -m branchName")
            return False
        if k.buildType == "node":
            k.build.buildNode()
        elif k.buildType == "tomcat":
            k.build.buildMaven()
            k.build.buildMavenTomcat()
        else:## jar
           k.build.buildMaven()
    elif k.build.action == "sonar":
        sonar(k.build.serverName,k.mvn,k.build.masterDir)
    elif k.build.action == "changmen":
        # 用于批量远程修改tomcat 启动参数 不用重新部署
        k.execAnsible(serverName,deploynode, k.build.action, k.build.envName,k.buildType)
    elif k.build.action == "changxml":
        # 用于批量远程修改tomcat 服务参数启动参数 不用重新部署72
        k.execAnsible(serverName,deploynode, k.build.action, k.build.envName,k.buildType)
    elif k.build.action == "deploy":
        if k.buildType == "node":
            k.build.buildNode()
            k.execAnsible(serverName,deploynode, "back", k.build.envName,k.buildType)
            k.delployNodeDir(serverName,k.build.envName)
        elif k.buildType == "tomcat":
            k.build.buildMaven()
            k.build.buildMavenTomcat()
        else:
            if not k.build.buildMaven():
                print("build False")
                sys.exit(1)
        k.execAnsible(serverName,deploynode, "stop", k.build.envName,k.buildType)
        k.execAnsible(serverName, deploynode,"back", k.build.envName,k.buildType)
        #清理部署root目录 历史部署文件
        if k.buildType == "tomcat":
            k.execAnsible(serverName,deploynode, "delroot", k.build.envName,k.buildType)
            k.execAnsible(serverName, deploynode,"delwar", k.build.envName,k.buildType)
        # 部署新包至目标节点
        if k.buildType == "node":
            k.delployNodeDir(serverName, k.build.envName)
        else:
            k.sendToNode(serverName, deploynode,k.buildType)
            if not k.execAnsible(serverName,deploynode, "start", k.build.envName,k.buildType):
                sys.exit(1)
    elif k.build.action == "restart":
        k.execAnsible(serverName, deploynode, "stop", k.build.envName, k.buildType)
        k.execAnsible(serverName, deploynode, "start", k.build.envName, k.buildType)
    elif k.build.action == "reinstall":
        k.execAnsible(serverName, deploynode, "reinstall", k.build.envName, k.buildType)
    elif k.build.action == "merge":
        # 合并分支
        if k.build.mbranchName and k.build.branchName != "master":
            k.git.merge(k.build.branchName, k.build.mbranchName)
            return True
        myloger(name=k.build.serverName, msg="follow -b branchName -m mBrancherName")
    elif k.build.action == "init":
        # git仓库本地初始化
        k.git.init(serverName,k.build.masterDir,k.build.gitUrl)
    elif k.build.action == "reinit":
        # git仓库本地重新初始化
         k.git.reinit(serverName,k.build.masterDir,k.build.gitUrl)
    elif k.build.action == "send":
        if k.buildType == "node":
            k.build.buildNode()
        else:
           if not k.build.buildMaven():
               print("build False")
               sys.exit(1)
        k.execAnsible(serverName, deploynode, "back", k.build.envName, k.buildType)
        if k.buildType == "tomcat":
            k.execAnsible(serverName, deploynode, "delwar", k.build.envName, k.buildType)
        if k.buildType !="node":
            k.sendToNode(serverName, deploynode, k.buildType)
        else:
            k.delployNodeDir(serverName, k.build.envName)

    elif k.build.action == "rollback":
        # git仓库本地重新初始化
        # k.rollback()
        k.execAnsible(serverName, deploynode, "rollback", k.build.envName, k.buildType)
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
        # 获取部署状态
        return k.execAnsible(serverName, deploynode, k.build.action, k.build.envName, k.buildType)
        # k.getStatus()
        # k.getHistoryVersion()
    else:
        myloger(name=k.build.serverName, msg="follow -n serverName -a action[build,deploy,rollback,status,init,reinit,merge]"
                                             " -b branchName -m mBranch"
                                             " -e envName -v versionId1")
        return False

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
        serverConf = "/silencedeploy/config/startService-normal-{envName}.yaml".format(envName=envName)
        gitsysConfig = confDict["gitsys"]["gitsysConfig"]
        gitsysConfigDir = confDict["gitsys"]["gitsysConfigDir"]
        if not os.path.exists(gitsysConfigDir):
            git.init("","sysconfig", gitsysConfigDir, gitsysConfig)
    else:
        myloger(name=serverName, msg="类型错误:%s" % projectName)
        sys.exit()
    serverDict = readYml(serverConf)
    startConf = confDict["startServer"].format(envName=envName, projectName=projectName)
    deploythreadNum = confDict["deploythreadNum"]
    buildthreadNum = confDict["buildthreadNum"]
    resultYml = confDict["resultYml"].format(envName=envName)
    if action == "reset":
        # 因错误的执行或者强制停止可以重置启动文件，控制从第一个工程执行操作
        cleanfile(startConf)
        myloger(name="consle", msg="情况启动文件顺序:%s" % startConf)
        sys.exit()
    if serverName == "all":
        sortlist = sortedServerName(serverDict)
        tpool=[]
        if action in ["deploy", "reinstall","redeploy","restart", "canary", "rollback","status"]:
            for serName in sortlist:
                if serName == "all":
                    continue
                if not serverDict[serName]["Parallel"]:
                    myloger(name=serName, msg="单线程执行:%s" % serName)
                    main(serName, serverConf, envConf)
                else:
                    tpool.append(serName)
            threadPool(tpool, deploythreadNum, main, serverConf, envConf)
        elif action in ["build1",'status']:
            threadPool(sortlist, buildthreadNum, main, serverConf, envConf)
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
                main(serName, serverConf, envConf)
                myloger(name=serName, msg="等待2s")
                time.sleep(2)
        # showResult(resultYml, action, serverName)
        cleanfile(startConf)
    else:
        if serverName not in serverDict:
            myloger(name=serverName, msg="%s:服务名错误" % serverName)
            printServerName(serverDict)
            sys.exit()
        main(serverName, serverConf, envConf)
        # showResult(resultYml, action, serverName)
        cleanfile(startConf)
if __name__ == "__main__":
    parallel()