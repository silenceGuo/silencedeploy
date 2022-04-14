#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 2021-1-7 下午 13:19 
# @Author : damon.guo 
# @File : deploy_control.py 
# @Software: PyCharm
import yaml
from tornado import template
from concurrent.futures import ThreadPoolExecutor,as_completed
from func_timeout import func_set_timeout
import func_timeout
import sys
import datetime
# from git_control import git
# from build_control import build
# import common
import os
import threading
import time
from tools.git_control import git
from tools.build_control import build
from tools.common import *
"""
按照项目分，代码的拉取方式。和代码的部署方式，定义在配置文件中，增加项目选项 -p
"""
class k8s():
    def __init__(self, serverConf,envConf,serverName):
        self.build = build(serverConf, envConf, serverName)
        self.k8sTmp = self.build.confDict["k8sTmp"].format(envName=self.build.envName,buildType=self.build.buildType)
        self.ingressTmp = self.build.confDict["ingressTmp"].format(envName=self.build.envName)
        self.codeType = self.build.serverDict[serverName]["codeType"]
        self.buildType = self.build.serverDict[serverName]["buildType"]
        if self.codeType == "git":
            self.git = git(serverConf, serverName)
        else:
            self.svn = svn(serverConf, serverName)
        self.hpaTmp = self.build.confDict["k8shpaTmp"]
        self.tmpOutDir = self.build.confDict["tmpOutDir"]
        if not os.path.exists(self.tmpOutDir):
            os.makedirs(self.tmpOutDir)
        self.keepDeploymentYmlNum = self.build.confDict["keepDeploymentYmlNum"]
        self.kubectl = self.build.confDict["kubectl"]
        self.mvn = self.build.confDict["mvnPath"]
        self.kubeconfig = self.build.confDict["kubeconfig"].format(envName=self.build.envName)

    def genConfigFile(self):
        self.build.versionID = self.build.getVersion()
        if not self.build.versionID:
            self.build.versionID = self.build.genVersion()
        self.imgUrl = "{repositoryUrl}/{nameSpace}/{serverName}:{env}.{version}".format(
            repositoryUrl=self.build.vpcrepUrl,
            nameSpace=self.build.nameSpace,
            serverName=self.build.serverName,
            env=self.build.envName,
            version=self.build.versionID)
        configvalues = {
            "JOB_NAME": self.build.serverName,
            "ENV_NAME": self.build.envName,
            "VERSIONID": self.build.versionId,
            "IMAGE_URL": self.imgUrl,
            "PORT": self.build.Port,
            "REPLICAS": self.build.replicas,
            "cpuLimits": self.build.cpuLimits,
            "menLimits": self.build.menLimits,
            "menRequests": self.build.menRequests,
            "hpaMax": self.build.hpaMax,
            "hpaCPU": self.build.hpaCPU,
            # "URL": self.build.url,
            "URL": self.build.url.format(envName=self.build.envName), # 以后根据环境取
        }
        if self.build.action == "canary":
           self.k8sTmp = self.build.confDict["canaryTmp"]
        self.k8sIngressTmp = self.build.confDict["ingressTmp"].format(envName=self.build.envName)
        deployDir = os.path.join(self.tmpOutDir, "deploy", "{0}-{1}".format(self.build.serverName, self.build.envName))
        if not os.path.exists(self.tmpOutDir):
            os.makedirs(self.tmpOutDir)
        if not os.path.exists(deployDir):
            os.makedirs(deployDir)
        self.deployfile = os.path.join(deployDir, "{serverName}-{envName}-{versionID}.deploy.yaml".format(
            serverName=self.build.serverName, envName=self.build.envName, versionID=self.build.versionID))

        self.ingressfile = os.path.join(deployDir, "{serverName}-{envName}-{versionID}.ingress.yaml".format(
            serverName=self.build.serverName, envName=self.build.envName, versionID=self.build.versionID))

        self.hpafile = os.path.join(deployDir, "{serverName}-{envName}-{versionID}.hpa.yaml".format(
            serverName=self.build.serverName, envName=self.build.envName, versionID=self.build.versionID))

        myloger(name=self.build.serverName,
                       msg="生成%s k8s deployment部署文件:%s" % (self.build.serverName, self.deployfile))
        genTmpFile(self.build.serverName, configvalues, self.k8sTmp, self.deployfile)
        myloger(name=self.build.serverName, msg="生成%s k8s HPA部署文件:%s" % (self.build.serverName, self.hpafile))
        genTmpFile(self.build.serverName, configvalues, self.hpaTmp, self.hpafile)

        if self.build.url:
            myloger(name=self.build.serverName,
                             msg="生成%s k8s Ingress部署文件:%s" % (self.build.serverName, self.ingressfile))
            genTmpFile(self.build.serverName, configvalues, self.k8sIngressTmp, self.ingressfile)

        # if self.build.DubboPort:
        #     self.dubboPortfile = os.path.join(deployDir, "{serverName}-{envName}-{versionID}.dubboPort.yaml".format(
        #     serverName=self.build.serverName, envName=self.build.envName, versionID=self.build.versionID))
        #     common.myloger(name=self.build.serverName,
        #                    msg="生成%s k8s nodePort部署文件:%s" % (self.build.serverName, self.deployfile))
        #     common.genTmpFile(self.build.serverName, configvalues, self.dubboPortTmp, self.dubboPortfile)

    def getHistoryVersion(self):
        common.myloger(name=self.build.serverName, msg="获取应用:{serverName},历史版本信息,名称空间:{namespace}".format(
            serverName=self.build.serverName, namespace=self.build.envName, versionId=self.build.versionId))
        historyDict = {}
        stdout, stderr = common.execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} rollout history deployment/{severName}-{envName} -n {envName}".format(
            severName=self.build.serverName, envName=self.build.envName,kubectl=self.kubectl,kubeconfig=self.kubeconfig
        ))
        historylist = stdout.split('\n')[2:]
        historylisttmp=[]
        for i in historylist:
            sublist = [j for j in i.split(" ") if j]
            if sublist:
                historylisttmp.append(str(sublist[0]))
        historyDict[self.build.serverName] = historylisttmp
        return historyDict

    def cleanDeployYml(self):
        # 清理历史部署文件
        deployDir = os.path.join(self.tmpOutDir, "deploy", "{0}-{1}".format(self.build.serverName,self.build.envName))
        ymlList = os.listdir(deployDir)
        ymlList.sort()
        FileNum = len(ymlList)
        # removeFileList = ymlList[:(FileNum-self.keepDeploymentYmlNum)] #[ :12-20]
        if FileNum > self.keepDeploymentYmlNum:
            removeFileList = ymlList[:(FileNum - self.keepDeploymentYmlNum)]
            for i in removeFileList:
                f = os.path.join(deployDir, i)
                common.myloger(name=self.build.serverName, msg="清理应用:{serverName}历史应用部署文件:{filename}".format(
                    serverName=self.build.serverName, filename=f
                ))
                os.remove(f)
            common.myloger(name=self.build.serverName, msg="清理应用:{serverName}历史应用部署文件总数:{num}".format(
                serverName=self.build.serverName, num=len(removeFileList)
            ))

    def delpoyK8S(self):
        self.genConfigFile()
        # self.dubboPortfile
        # sys.exit()

        myloger(name=self.build.serverName, msg="部署服务:%s k8s部署文件:%s" % (self.build.serverName, self.deployfile))
        execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} apply -f {configfile} --record".format(
            configfile=self.deployfile, kubectl=self.kubectl, kubeconfig=self.kubeconfig
            ))

        myloger(name=self.build.serverName,
                         msg="部署HPA服务:%s k8s部署文件:%s" % (self.build.serverName, self.hpafile))
        execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} apply -f {configfile} --record".format(
            configfile=self.hpafile, kubectl=self.kubectl, kubeconfig=self.kubeconfig
        ))

        if self.build.url:
            myloger(name=self.build.serverName,
                             msg="部署ingress服务:%s k8s部署文件:%s" % (self.build.serverName, self.ingressfile))
            execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} apply -f {configfile} --record".format(
                configfile=self.ingressfile, kubectl=self.kubectl, kubeconfig=self.kubeconfig
            ))
        # if self.build.DubboPort:
        #     common.myloger(name=self.build.serverName,
        #                    msg="部署nodePort:%s k8s部署文件:%s" % (self.build.serverName, self.ingressfile))
        #     common.execSh(self.build.serverName,
        #                   "{kubectl} --kubeconfig {kubeconfig} apply -f {configfile} --record".format(
        #                       configfile=self.dubboPortfile, kubectl=self.kubectl, kubeconfig=self.kubeconfig
        #                   ))
        self.cleanDeployYml()
        # resultstatusDict = common.showResult(self.build.resultYml, self.build.action,self.build.serverName)
        # resultstatusDict = common.readYml(self.build.resultYml)
        statusDict = result(self.build.resultYml, self.build.serverName)
        # common.showResult(self.build.resultYml, action, serverName)
        try:
            res = checkDeployStatus(self.build.serverName, self.kubectl, self.build.envName, self.kubeconfig)
            # statusDict[self.build.serverName]["deployResult"] = "True"
            # common.writeYml(self.build.resultYml, statusDict)
            statusDict[self.build.serverName]["deployResult"] = res
            writeYml(self.build.resultYml, statusDict)
        except func_timeout.exceptions.FunctionTimedOut:
            myloger(name=self.build.serverName,
                           msg="部署服务:%s 检查服务更新状态超时！" % (self.build.serverName))
            statusDict[self.build.serverName]["deployResult"] = "timeout"
            writeYml(self.build.resultYml, statusDict)


        # common.checkDeployStatus(self.build.serverName, self.kubectl, self.build.envName, self.kubeconfig)
        # if action == "deploy" or action == "redeploy":
        #     common.checkDeployStatus(serName, kubectl, envName, kubeconfig)

    def canary(self):
        self.genConfigFile()
        common.myloger(name=self.build.serverName, msg="金丝雀部署服务:%s k8s部署文件:%s" % (self.build.serverName, self.configfile))
        common.execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} apply -f {configfile} --record".format(
            configfile=self.configfile, kubectl=self.kubectl, kubeconfig=self.kubeconfig
            ))
        self.cleanDeployYml()

    def getStatus(self):
        common.myloger(name=self.build.serverName, msg="获取负载应用状态:%s,名称空间:%s" % (self.build.serverName, self.build.envName))
        common.execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} get deployment {serverName}-{envName} -n {namespace} -o wide".format(
            serverName=self.build.serverName, namespace=self.build.envName, envName=self.build.envName,kubectl=self.kubectl,
            kubeconfig=self.kubeconfig
        ))

        common.myloger(name=self.build.serverName, msg="获取服务状态:%s,名称空间:%s" % (self.build.serverName, self.build.envName))
        common.execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} get svc {serverName}-{envName} -n {namespace} -o wide".format(
            serverName=self.build.serverName, namespace=self.build.envName, envName=self.build.envName, kubectl=self.kubectl,
            kubeconfig=self.kubeconfig))
    def reDeploy(self):
        " 重新部署原来的工程，配置保持不变，相当于重启"
        "kubectl rollout restart deployment demo-dev -n dev"
        # self.delpoyK8S()
        common.execSh(self.build.serverName, "{kubectl} --kubeconfig {kubeconfig} rollout restart deployment {serverName}-{envName} -n {envName}".format(
            serverName=self.build.serverName,
            envName=self.build.envName,
            kubectl=self.kubectl,
            kubeconfig=self.kubeconfig
        ))
        common.checkDeployStatus(self.build.serverName, self.kubectl, self.build.envName, self.kubeconfig)

    def rollback(self):
        historyDict = self.getHistoryVersion()
        # 回退上一个版本
        if self.build.versionId in historyDict[self.build.serverName]:
            common.myloger(name=self.build.serverName, msg="回滚应用:{serverName},找到指定版本，指定版本:{versionId},名称空间:{namespace}".format(
                serverName=self.build.serverName, namespace=self.build.envName, versionId=self.build.versionId))
            common.execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} rollout undo deployment/{serverName}-{envName} -n {envName} --to-revision={versionId}".format(
            serverName=self.build.serverName, envName=self.build.envName, versionId=self.build.versionId,kubectl=self.kubectl,
            kubeconfig=self.kubeconfig))
        else:
            common.myloger(name=self.build.serverName, msg="回滚应用:{serverName},未找到指定版本，默认上一个版本,名称空间:{namespace}".format(
                serverName=self.build.serverName, namespace=self.build.envName, versionId=self.build.versionId))
            common.execSh(self.build.serverName,"{kubectl} --kubeconfig {kubeconfig} rollout undo deployment/{serverName}-{envName} -n {envName}".format(
            serverName=self.build.serverName, envName=self.build.envName,kubectl=self.kubectl,kubeconfig=self.kubeconfig))
        common.checkDeployStatus(self.build.serverName, self.kubectl, self.build.envName, self.kubeconfig)

def main(serverName,serverConf,envConf):
    # options = Options()
    options, args = common.getOptions()
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
    svnUser = k.build.confDict["svnsys"]["svnUser"]
    svnPasswd = k.build.confDict["svnsys"]["svnPasswd"]
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
        common.myloger(name=k.build.serverName, msg="follow -n serverName -a action[build,deploy,rollback,status,init,reinit,merge]"
                                             " -b branchName -m mBranch"
                                             " -e envName -v versionId1")
        return False


def parallel():
    options, args = common.getOptions()
    serverName = options.serverName
    projectName = options.projectName
    envName = options.envName
    action = options.action
    envConf = "/python_yek/xkj-k8s/env.yaml"
    confDict = common.readYml(envConf)
    if projectName == "node":
        serverConf = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
    elif projectName == "springcloud":
        serverConf = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
    elif projectName == "xkj":
        serverConf = "/python_yek/xkj-k8s/xkj/xkj-config-{envName}.yaml".format(envName=envName)
        # serverConf = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
        gitsysConfig = confDict["gitsys"]["gitsysConfig"]
        gitsysConfigDir = confDict["gitsys"]["gitsysConfigDir"]
        if not os.path.exists(svnsysConfigDir):
            common.Svninit("sysconfig", svnsysConfig, svnsysConfigDir, svnUser, svnPasswd)
        if not os.path.exists(gitsysConfigDir):
            common.Gitinit("sysconfig", gitsysConfig, gitsysConfigDir)
        # sys.exit(1)
    else:
        common.myloger(name=serverName, msg="类型错误:%s" % projectName)
        sys.exit()
    serverDict = common.readYml(serverConf)
    startConf = confDict["startServer"].format(envName=envName, projectName=projectName)
    threadNum = confDict["threadNum"]
    kubeconfig = confDict["kubeconfig"].format(envName=envName)
    kubectl = confDict["kubectl"]
    resultYml = confDict["resultYml"].format(envName=envName)
    if action == "reset":
        # 因错误的执行或者强制停止可以重置启动文件，控制从第一个工程执行操作
        common.cleanfile(startConf)
        common.myloger(name="consle", msg="情况启动文件顺序:%s" % startConf)
        sys.exit()
    # threadPool = ThreadPoolExecutor(max_workers=threadNum, thread_name_prefix="test_")
    if serverName == "all":
        sortlist = common.sortedServerName(serverDict)
        tpool=[]
        # if action in ["deploy","status", "build", "restart", "redeploy", "canary", "rollback"]:
        if action in ["deploy", "redeploy","restart", "canary", "rollback","status"]:
            for serName in sortlist:
                if serName == "all":
                    continue
                if not serverDict[serName]["Parallel"]:
                    common.myloger(name=serName, msg="单线程执行:%s" % serName)
                    main(serName, serverConf, envConf)
                else:
                    # common.myloger(name=serName, msg="多线程执行:%s，并发线程数:%s" % (serName, threadNum))
                    # obj = threadPool.submit(main, serName, serverConf, envConf)
                    tpool.append(serName)
            # for future in as_completed(tpool):
            #     data = future.result()
            #     common.myloger(name=name, msg="线程执行完成!")
            # threadPool.shutdown(wait=True)
            common.threadPool(tpool, threadNum, main, serverConf, envConf)

            # common.myloger(name=name, msg="线程执行完成!")
            # common.myloger(name=serName, msg="执行完成:%s" % serName)
        elif action in ["build1",'status']:
            # common.threadPool2(sortlist, threadNum, main, [serverConf], [envConf])
            common.threadPool(sortlist, threadNum, main, serverConf, envConf)
        else:
            if common.readfile(startConf):
                serName, point = common.readfile(startConf)
            else:
                point = 0
            for serName in sortlist[int(point):]:
                if serName == "all":
                    continue
                ser_index = sortlist.index(serName)
                info = "%s:%s" % (ser_index, serName)
                common.writhfile(startConf, info)
                main(serName, serverConf, envConf)
                common.myloger(name=serName, msg="等待2s")
                time.sleep(2)
        common.showResult(resultYml, action, serverName)
        common.cleanfile(startConf)
    else:
        if not serverDict.has_key(serverName):
            common.myloger(name=serverName, msg="%s:服务名错误" % serverName)
            common.printServerName(serverDict)
            sys.exit()
        main(serverName, serverConf, envConf)
        common.showResult(resultYml, action, serverName)
        common.cleanfile(startConf)

if __name__ == "__main__":
    parallel()
