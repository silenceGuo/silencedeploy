#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 2020-9-29 上午 11:42 
# @Author : damon.guo 
# @File : buildInit.py 
# @Software: PyCharm
from tools.git_control import git
from tools.common import *
import os
import datetime
import shutil
import sys

class build():
    def __init__(self, serverConf,envConf,severName):
        options, args = getOptions()
        self.action = options.action
        # self.serverName = options.serverName
        self.serverName = severName
        self.branchName = options.branchName
        self.mbranchName = options.mbranchName
        self.versionId = options.versionId
        self.envName = options.envName
        self.typeName = options.typeName
        self.serverDict = readYml(serverConf)
        self.confDict = readYml(envConf)
        self.tmpOutDir = self.confDict["tmpOutDir"]
        self.mvn = self.confDict["mvnPath"]
        self.npm = self.confDict["npmPath"]
        self.node = self.confDict["nodePath"]
        self.npmRepo = self.confDict["npmRepo"]
        self.javaHome = self.confDict["javaHome"]
        self.javaPath = self.confDict["javaPath"]
        self.resultYml = self.confDict["resultYml"].format(envName=self.envName)
        self.jarPath = self.confDict["jarPath"]
        self.dockerfileDir = self.confDict["dockerfileDir"]
        self.nodeNginxConf = self.confDict["nodeNginxConf"].format(envName=self.envName)

        self.buildDir = self.serverDict[self.serverName]["buildDir"].format(envName=self.envName)
        self.codeType = self.serverDict[self.serverName]["codeType"]
        self.buildType = self.serverDict[self.serverName]["buildType"]
        self.sysConfigDir = self.confDict["gitsys"]["gitsysConfigDir"]
        if self.codeType == "git":
            self.git = git(serverConf, self.serverName)
            self.gitUrl = self.serverDict[self.serverName][self.codeType]["gitUrl"]
        else:
            myloger("olny support git")
        self.masterDir = self.serverDict[self.serverName][self.codeType]["masterDir"].format(envName=self.envName)
        # print("url{env}".format(env=self.envName))
        # if "url{env}".format(env=self.envName) in self.serverDict[self.serverName]:
        #     self.url = self.serverDict[self.serverName]["url{env}".format(env=self.envName)]
        #     print(self.url)
        #     sys.exit()
        # 两种方式区分环境部署不同的域名，一个是通过一个域名，一个适用，不同域名
        if "url" in self.serverDict[self.serverName]:
            self.url = self.serverDict[self.serverName]["url"].format(envName=self.envName)
        else:
            self.url = ""
        if self.buildType == "node":
             self.nodeversion = self.serverDict[self.serverName]["nodeversion"]
        if self.buildType == "tomcat":
             self.targetDir = self.serverDict[self.serverName]["targetDir"].format(envName=self.envName)

        self.deployFile = self.serverDict[self.serverName]["deployFile"].format(envName=self.envName)
        self.repUrl = self.confDict["imageRepo-{envName}".format(envName=self.envName)]["url"]
        self.vpcrepUrl = self.confDict["imageRepo-{envName}".format(envName=self.envName)]["vpcurl"]
        self.nameSpace = self.confDict["imageRepo-{envName}".format(envName=self.envName)]["nameSpace"]
        self.userName = self.confDict["imageRepo-{envName}".format(envName=self.envName)]["userName"]
        self.passWord = self.confDict["imageRepo-{envName}".format(envName=self.envName)]["passWord"]
        self.http_port = self.serverDict[self.serverName]["http_port"]
        # self.replicas = self.serverDict[self.serverName]["replicas"]
        # self.hpaMax = self.serverDict[self.serverName]["hpaMax"]
        # self.hpaCPU = self.serverDict[self.serverName]["hpaCPU"]

    def addResource(self):
        self.targetDir = self.serverDict[self.serverName]["targetDir"].format(envName=self.envName)
        # self.sysConfigDir = self.confDict["svnsysConfigDir"]
        serverNameEnvConfDir = os.path.join(self.sysConfigDir, self.serverName, "resources-%s") % self.envName
        os.chdir(self.sysConfigDir)
        myloger(name=self.serverName, level="INFO", msg="获取新配置")
        if self.codeType == "git":
            stdout, stderr = execSh(self.serverName, "git pull")
        else:
            myloger("olny support git")
        if os.path.exists(self.targetDir):
            myloger(self.serverName,msg="清理默认的resources目录")
            shutil.rmtree(self.targetDir)
        try:
            myloger(name=self.serverName,msg="copy sysconfig Dir :%s to:%s" % (serverNameEnvConfDir, self.targetDir))
            shutil.copytree(serverNameEnvConfDir,  self.targetDir)
        except Exception as e:
            myloger(name=self.serverName,msg="%s dir is exists！" % e)
            sys.exit(1)

    def buildMaven(self):
        if not os.path.exists(self.buildDir):
            myloger(name=self.serverName, level="INFO", msg="项目未初始化,请初始化")
            sys.exit()
        myloger(name=self.serverName, msg="%s Maven构建,工作目录：%s" % (self.serverName, self.buildDir))
        # self.git.pull(self.mbranchName)
        if self.action == "rebuild":
            pass
        else:
            self.git.pull(self.mbranchName)
        if self.serverName == "xkj-job-admin":
            # 针对job-admin工程处理，需要先对配置文件修改在进行打包构建
            self.addResource()
        myloger(name=self.serverName, level="INFO", msg="切换构建工作目录:%s" % self.buildDir)
        os.chdir(self.buildDir)
        ###  -T 4 参数是指定 线程数 4个
        cmd = "%(mvn)s clean && %(mvn)s -T 4 install -Dmaven.test.skip=true -Dmaven.compile.fork=true" % {"mvn": self.mvn}
        # cmd = "%(mvn)s clean && %(mvn)s -T 4 install org.apache.maven.plugins:maven-deploy-plugin:2.8:deploy -DskipTests -Dmaven.compile.fork=true" % {"mvn": self.mvn}
        stdout, stderr = execSh(self.serverName, cmd)
        statusDict = result(self.resultYml, self.serverName)
        if "BUILD FAILURE" in stdout:
            myloger(name=self.serverName, level="ERROR", msg="Maven构建失败,结果检查输出文件：%s" % self.resultYml)
            statusDict[self.serverName]["buildMavenResult"] = False
            statusDict[self.serverName]["deployResult"] = False
            writeYml(self.resultYml,statusDict)
            return False
        elif "BUILD FAILURE" in stderr:
            myloger(name=self.serverName, level="ERROR", msg="Maven构建失败,结果检查输出文件：%s" % self.resultYml)
            statusDict[self.serverName]["buildMavenResult"] = False
            statusDict[self.serverName]["deployResult"] = False
            writeYml(self.resultYml, statusDict)
            return False
        else:
            myloger(name=self.serverName, level="INFO", msg="Maven构建成功,结果检查输出文件：%s" % self.resultYml)
            # writhfile(self.buildResult, "%s build maven success!" % self.serverName)
            statusDict[self.serverName]["buildMavenResult"] = True
            statusDict[self.serverName]["deployResult"] = False
            writeYml(self.resultYml, statusDict)
            # print(readYml(self.resultYml))
            return True

    def buildMavenTomcat(self):
        # serverNameDict = projectDict[serverName]
        # serverDict = getDeploymentTomcatPath(serverName)
        ###############
        if not os.path.exists(self.buildDir):
            myloger(name=self.serverName, level="INFO", msg="项目未初始化,请初始化")
            sys.exit()
        if self.buildType == "tomcat":
            os.chdir(self.sysConfigDir)
            myloger(name=self.serverName, level="INFO", msg="获取新配置")
            stdout, stderr = execSh(self.serverName, "git pull")
        ###############
        # 判断是否有git 执行错误
        # isNoErr(stdout, stderr)
        serverNameEnvConfDir = os.path.join(self.sysConfigDir, self.serverName, "sys-%s") % self.envName
        serverSysConfigDir = os.path.join(self.targetDir, "WEB-INF/classes/resouce/sys")
        if os.path.exists(serverSysConfigDir):
            myloger(name=self.serverName, level="INFO", msg="清理默认的sys目录,删除%s" % serverSysConfigDir)
            shutil.rmtree(serverSysConfigDir)
        try:
            msg = "copy sysconfig Dir :%s to:%s" % (serverNameEnvConfDir, serverSysConfigDir)
            myloger(name=self.serverName, level="INFO", msg=msg)
            shutil.copytree(serverNameEnvConfDir, serverSysConfigDir)
        except Exception as e:
            msg = "dir is exists! %s" % e
            myloger(name=self.serverName, level="INFO", msg=msg)
            sys.exit(1)
        os.chdir(self.targetDir)
        cmd = '%s -cvf %s *' % (self.jarPath, self.deployFile.format(envName=self.envName))
        myloger(name=self.serverName, level="INFO", msg="重新封装打包")
        execSh(self.serverName,cmd)
        myloger(name=self.serverName, level="INFO", msg="重新封装打包完成")

    def genCatalinaforK8S(self):
        dicttmp = {}
        """修改tocmat 启动内存参数，批量部署根据每个服务名的设置，调整完需要重启服务。"""
        self.menLimits = self.serverDict[self.serverName]["limits"]["memory"]
        self.menRequests = self.serverDict[self.serverName]["requests"]["memory"]
        self.startMemory = self.serverDict[self.serverName]["requests"]["startMemory"]
        # self.jmxPort = self.serverDict[self.serverName]["jmxPort"]
        # dicttmp["jmxPort"] = self.jmxPort
        tmp = self.confDict["tomcatCatalinaTmp"]
        servertmp = self.confDict["tomcatServerTmp"]
        copyFile(self.serverName,servertmp,self.buildDir)
        # dicttmp["jmxPort"] = self.jmxPort
        CatalinaPath = os.path.join(self.buildDir, "catalina.sh")
        # xms = self.menLimits - 512
        xmx = self.startMemory
        dicttmp["xms"] = self.startMemory
        dicttmp["xmx"] = self.startMemory
        # xmn = str(int(xmx/2 * (3.0 / 8)))
        xmn = str(int(xmx/2))
        dicttmp["xmn"] = xmn
        # 应用skywalking 增加环境名称
        dicttmp["pinpointid"] = self.serverName + self.envName
        # dicttmp["pinpointid"] = serverName + ip[-1:4]
        genTmpFile(self.serverName,dicttmp,tmp,CatalinaPath)
    def genCatalina(self):
        dicttmp = {}
        """修改tocmat 启动内存参数，批量部署根据每个服务名的设置，调整完需要重启服务。"""
        self.xmx = self.serverDict[self.serverName]["xmx"]
        self.xms = self.serverDict[self.serverName]["xms"]
        self.jmxPort = self.serverDict[self.serverName]["jmxPort"]
        dicttmp["jmxPort"] = self.jmxPort
        tmp = self.confDict["tomcatCatalinaTmp"]
        servertmp = self.confDict["tomcatServerTmp"]
        copyFile(self.serverName,servertmp,self.buildDir)
        CatalinaPath = os.path.join(self.buildDir, "catalina.sh")
        # xms = self.menLimits - 512
        xmx = self.xmx
        dicttmp["xms"] = self.xms
        dicttmp["xmx"] = self.xmx
        # xmn = str(int(xmx/2 * (3.0 / 8)))
        xmn = str(int(xmx/2))
        dicttmp["xmn"] = xmn
        # 应用skywalking 增加环境名称
        dicttmp["pinpointid"] = self.serverName + self.envName
        # dicttmp["pinpointid"] = serverName + ip[-1:4]
        genTmpFile(self.serverName,dicttmp,tmp,CatalinaPath)
    def buildImageTomcat(self):
        tag = self.genVersion()
        self.genCatalinaforK8S()
        # sys.exit()
        myloger(name=self.serverName, msg="构建镜像:%s" % (self.serverName))
        # 切换工作目录
        os.chdir(self.masterDir)
        dockerFile = os.path.join(self.dockerfileDir, "Dockerfile.{buildType}".format(buildType=self.buildType))
        Dockerfile = os.path.join(self.masterDir, "Dockerfile")

        copyFile(self.serverName, dockerFile, Dockerfile)
        # 增加skywalking 监测端
        skywalkingAgentTmp = self.confDict["skywalkingAgent"].format(envName=self.envName)
        skywalkingAgentDeply = os.path.join(self.masterDir, "agent")
        if os.path.exists(skywalkingAgentDeply):
            shutil.rmtree(skywalkingAgentDeply)
        myloger(name=self.serverName,
                       msg="%s 部署skywalking agent!" % (self.deployFile.format(envName=self.envName)))
        copyDir(self.serverName, skywalkingAgentTmp, skywalkingAgentDeply)

        warPath = self.deployFile.format(envName=self.envName).split(self.masterDir)[-1]
        if not os.path.exists(self.deployFile.format(envName=self.envName)):
            myloger(name=self.serverName,
                             msg="%s is not exist,buildMavn First!" % (self.deployFile.format(envName=self.envName)))
            return False
        buildImage = "docker build -t {repositoryUrl}/{nameSpace}/{serverName}:{env}.{tag} " \
                     "--build-arg WarName={WarName} --no-cache .".format(repositoryUrl=self.repUrl,
                                                                         serverName=self.serverName,
                                                                         env=self.envName,
                                                                         nameSpace=self.nameSpace,
                                                                         tag=tag,
                                                                         dockerPort=self.http_port,
                                                                         WarName=warPath)

        imgUrl = buildImage.split(" ")[3]
        self.imgUrl = imgUrl
        os.chdir(self.masterDir)
        stdout, stderr = execSh(self.serverName, buildImage)
        if "Successfully" in stdout:
            myloger(name=self.serverName, msg="build images sucess:%s " % self.imgUrl)
            return True
        else:
            myloger(name=self.serverName, msg="build images fail:%s " % self.imgUrl)
            return False

    def moveJar(self):
        os.chdir(self.masterDir)
        self.jarName = self.deployFile.split("/")[-1]
        self.jarPath = os.path.join(self.masterDir, "jarDir")
        if not os.path.exists(self.jarPath):
            os.makedirs(self.jarPath)
        newJarPath = os.path.join(self.jarPath, self.jarName)
        if os.path.exists(newJarPath):
            myloger(name=self.serverName,
                             msg="清理{serverName}历史文件：{jar}".format(serverName=self.serverName,jar=newJarPath))
            os.remove(newJarPath)
        # sys.exit()
        shutil.copy(self.deployFile.format(envName=self.envName), self.jarPath)
        if not os.path.exists(newJarPath):
            myloger(name=self.serverName, msg="复制{jar} to {jarPath} 失败!".format(jar=self.deployFile.format(envName=self.envName),jarPath=newJarPath))
        else:
            myloger(name=self.serverName,
                         msg="复制{jar} to {jarPath} 成功!".format(jar=self.deployFile.format(envName=self.envName), jarPath=newJarPath))
            return os.path.join("jarDir",self.jarName)

    def genVersion(self):
        # tmpOutDir = self.tmpOutDir
        myloger(name=self.serverName,msg="生成版本号!")
        versionDir = os.path.join(self.tmpOutDir, "versionDir")
        versionFile = os.path.join(self.tmpOutDir, "versionDir", "{serverName}-{envName}.txt".format(
            serverName=self.serverName, envName=self.envName
        ))
        if not os.path.exists(self.tmpOutDir):
            os.makedirs(self.tmpOutDir)
        if not os.path.exists(versionDir):
            os.makedirs(versionDir)
        dateNow = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
        versionID = "{dateNow}-{version}".format(dateNow=dateNow, version=self.versionId)
        # self.versionID = versionID
        with open(versionFile, "w+") as fd:
            myloger(name=self.serverName, msg="版本号:%s，写入文件:%s!" % (versionID,versionFile))
            fd.write(versionID)
        self.versionID = versionID
        myloger(name=self.serverName, msg="生成版本号:%s!" % self.versionID)
        return versionID

    def getVersion(self):
        self.tmpOutDir = self.confDict["tmpOutDir"]
        versionFile = os.path.join(self.tmpOutDir, "versionDir", "{serverName}-{envName}.txt".format(
            serverName=self.serverName, envName=self.envName
        ))
        if not os.path.exists(versionFile):
            return False
        with open(versionFile) as fd:
            versionID = fd.readline().strip()
        if not versionID:
            myloger(name=self.serverName, msg="未获取版本号:%s，文件:%s!" % (versionID, versionFile))
            return False
        else:
            myloger(name=self.serverName, msg="获取版本号:%s，文件:%s!" % (versionID, versionFile))
            return versionID

    def buildImage(self):
        tag = self.genVersion()
        # jarName = self.jar.split("/")[-1]
        newJarPath = self.moveJar()
        # sys.exit()
        # 拷贝 构建好的jar 包 到部署目录用于 构建镜像s
        # copyFile(serverName)
        self.startMemory = self.serverDict[self.serverName]["requests"]["startMemory"]
        xms = self.startMemory
        xmx = self.startMemory
        xmn = str(int(xmx/2))
        myloger(name=self.serverName, msg="构建镜像:%s" % (self.serverName))
        # 切换工作目录
        os.chdir(self.masterDir)
        dockerFile = os.path.join(self.dockerfileDir, "Dockerfile.{buildType}".format(buildType=self.buildType))
        Dockerfile = os.path.join(self.masterDir, "Dockerfile")
        copyFile(self.serverName,dockerFile, Dockerfile)
        # 增加skywalking 监测端
        skywalkingAgentTmp = self.confDict["skywalkingAgent"].format(envName=self.envName)
        skywalkingAgentDeply = os.path.join(self.masterDir, "agent")
        if os.path.exists(skywalkingAgentDeply):
            shutil.rmtree(skywalkingAgentDeply)
            # shutil.rmtree(serverSysConfigDir)
        myloger(name=self.serverName,
                       msg="部署skywalking agent!")
        copyDir(self.serverName, skywalkingAgentTmp, skywalkingAgentDeply)

        if not os.path.exists(self.deployFile.format(envName=self.envName)):
            myloger(name=self.serverName, msg="%s/%s is not exist,buildMavn First!" % (self.masterDir,self.deployFile.format(envName=self.envName)))
            return False
        buildImage = "docker build -t {repositoryUrl}/{nameSpace}/{serverName}:{env}.{tag} " \
                     "--build-arg envName={env} " \
                     "--build-arg dockerPort={dockerPort} " \
                     "--build-arg xmx={xmx} " \
                     "--build-arg xmn={xmn} " \
                     "--build-arg serverName={serverName} " \
                     "--build-arg jarName={jarName} --no-cache .".format(repositoryUrl=self.repUrl,
                                                              serverName=self.serverName,
                                                              env=self.envName,
                                                              nameSpace=self.nameSpace,
                                                              tag=tag,
                                                              xmx=xmx,
                                                              xmn=xmn,
                                                              dockerPort=self.http_port,
                                                              # jarName=self.deployFile
                                                              jarName=newJarPath
                                                                         )

        imgUrl = buildImage.split(" ")[3]
        self.imgUrl = imgUrl
        stdout, stderr = execSh(self.serverName,buildImage)
        if "Successfully" in stdout:
            myloger(name=self.serverName,msg="build images sucess:%s " % self.imgUrl)
            return True
        else:
            myloger(name=self.serverName, msg="build images fail:%s " % self.imgUrl)
            return False

    def switchNodeVersion(self):
        myloger(name=self.serverName, msg="%s node 切换版本：%s" % (self.serverName,self.nodeversion))
        stdout, stderr = execSh(self.serverName,"su - root -c 'nvm use %s'" % self.nodeversion)
        if "is not yet installed " in stderr:
            myloger(name=self.serverName, msg="目标服务器尝试执行 'nvm install %s' 在重试" % self.nodeversion)
            return False
        return True

    def buildNode(self):
        if not os.path.exists(self.buildDir):
            myloger(name=self.serverName, level="INFO", msg="项目未初始化,请初始化")
            sys.exit()
        if not self.switchNodeVersion():
            return False
        myloger(name=self.serverName, msg="%s node 构建" % self.serverName)

        self.git.pull(self.mbranchName)
        os.chdir(self.buildDir)
        myloger(name=self.serverName, msg="切换工作目录: %s " % self.buildDir)
        cmdset = "su - root -c 'cd {buildDir} && {npm} config set registry {npmRepo}'".format(buildDir=self.buildDir,npm=self.npm,npmRepo=self.npmRepo)
        stdout, stderr = execSh(self.serverName, cmdset)
        if "/usr/bin/env: node: No such file" in stderr:
            myloger(name=self.serverName, msg="目标服务器尝试执行 'ln -s %s /usr/bin/node' 在重试" % self.node)
            myloger(name=self.serverName, msg="目标服务器尝试执行 'ln -s %s /usr/bin/npm' 在重试" % self.npm)
            return False
        # cmd = "sudo {npm} install".format(npm=self.npm)
        cmd = "su - root -c 'cd {buildDir} && {npm} install'".format(buildDir=self.buildDir, npm=self.npm)
        stdout, stderr = execSh(self.serverName, cmd)

        cmdbuild = "su - root -c 'cd {buildDir} && {npm} run build-{envName}'".format(buildDir=self.buildDir, npm=self.npm,envName=self.envName)
        # cmdbuild = "su - root -c 'cd {buildDir} && {npm} run build-test'".format(buildDir=self.buildDir, npm=self.npm,envName=self.envName)
        stdout, stderr = execSh(self.serverName, cmdbuild)
        statusDict = result(self.resultYml, self.serverName)
        if "BUILD FAILURE" in stdout:
            myloger(name=self.serverName, level="ERROR", msg="NPM 构建失败")
            statusDict[self.serverName]["buildMavenResult"] = False
            writeYml(self.resultYml, statusDict)
            return False
        elif "BUILD FAILURE" in stderr:
            myloger(name=self.serverName, level="ERROR", msg="NPM 构建失败")
            statusDict[self.serverName]["buildMavenResult"] = False
            writeYml(self.resultYml, statusDict)
            return False
        else:
            statusDict[self.serverName]["buildMavenResult"] = True
            writeYml(self.resultYml, statusDict)
            return True

    def buildImageNode(self):
        tag = self.genVersion()
        jarName = self.deployFile.split("/")[-1]
        # 拷贝 构建好的jar 包 到部署目录用于 构建镜像s
        # copyFile(serverName)
        myloger(name=self.serverName, msg="构建镜像:%s" % (self.serverName))
        # 切换工作目录
        os.chdir(self.masterDir)
        dockerFile = os.path.join(self.dockerfileDir, "Dockerfile.{buildType}".format(buildType=self.buildType))
        Dockerfile = os.path.join(self.masterDir, "Dockerfile")
        copyFile(self.serverName,dockerFile, Dockerfile)
        # node采用nginx容器静态化部署，需要更新nginx 文件
        nginxConf = os.path.join(self.masterDir, "default.conf")
        copyFile(self.serverName,self.nodeNginxConf,nginxConf)
        if self.codeType == "git":
            self.git.pull(self.mbranchName)
        else:
            self.svn.svnUpdate()
        buildImage = "docker build -t {repositoryUrl}/{nameSpace}/{serverName}:{env}.{tag} " \
                     "--build-arg envName={env} " \
                     "--build-arg dockerPort={dockerPort} " \
                     "--no-cache .".format(repositoryUrl=self.repUrl,
                                                                         serverName=self.serverName,
                                                                         env=self.envName,
                                                                         nameSpace=self.nameSpace,
                                                                         tag=tag,
                                                                         dockerPort=self.http_port)

        imgUrl = buildImage.split(" ")[3]
        self.imgUrl = imgUrl
        stdout, stderr = execSh(self.serverName,buildImage)
        if "Successfully" in stdout:
            myloger(name=self.serverName, msg="build images sucess:%s " % self.imgUrl)
            return True
        else:
            myloger(name=self.serverName, msg="build images fail:%s " % self.imgUrl)
            return False

    def pushImage(self):
        myloger(name=self.serverName, msg="推送镜像:%s 至仓库 %s" % (self.imgUrl, self.repUrl))
        stdout, stderr = execSh(self.serverName,"docker push %s" % self.imgUrl)
        if "unauthorized to access repository" in stderr:
            myloger(name=self.serverName, msg="docker login %s first!" % self.repUrl)
            self.loginRepo()
            execSh(self.serverName,"docker push %s" % self.imgUrl)
        if "unauthorized: project not found" in stderr:
            myloger(name=self.serverName, msg="project is not found in %s !" % self.repUrl)
            # self.loginRepo()
            # execSh(self.serverName,"docker push %s" % self.imgUrl)
            sys.exit()

    def loginRepo(self):
        myloger(name=self.serverName, msg="登录镜像仓库 %s" % self.repUrl)
        docker_login = """sudo docker login --username={user} {repositoryUrl} -p {password}""".format(
            repositoryUrl=self.repUrl,
            user=self.userName,
            password=self.passWord
            )
        stdout, stderr = execSh(self.serverName,docker_login)

if __name__ == "__main__":
    ConfPATH = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
    g = build(ConfPATH, "/python_yek/xkj-k8s/env.yaml", "express-admin")
    g.genCatalina()
    
    g.buildNode()
    g.buildImageNode()
    # g.buildImageTomcat()
    g.pushImage()