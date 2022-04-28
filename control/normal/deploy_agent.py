#!/usr/bin/env python
# -*-coding:utf-8-*-
# @Author : gzq
# @date   : 2018/1/10 0010 16:30
# @file   : deploy-liunx.py
# 该脚本部署在统一的目录下通过，实现本地及远程服务器上的服务部署，重启，发布,分发,回滚等操作
# 登陆远程服务器需提前配置好ssh密钥登陆
import os
import xml.dom.minidom
import codecs
from collections import Counter
import sys
sys.path.append('/silencedeploy') ## 项目的绝对路径
from tools.common import *

class deployAgent():
    def __init__(self,serverconf,envName):
        self.confDict = readYml(serverconf)
        self.tomcatPrefix = self.confDict["tomcatPrefix"]
        self.baseTomcat = self.confDict["baseTomcat"]
        self.deploymentAppDir = self.confDict["deploymentAppDir"]
        self.checktime = self.confDict["checkTime"]
        self.java = self.confDict["javaPath"]
        self.nohup = self.confDict["nohup"]
        self.startConf = self.confDict["startServer"]
        self.ansibleHost = self.confDict["ansibileHost"]
        self.bakDir = self.confDict["bakDir"]
        self.logsPath = self.confDict["logsPath"]
        self.bakNum = self.confDict["bakNum"]
        self.logsPath = self.confDict["logsPath"]
        self.tomcatCatalinaTmp = self.confDict["tomcatCatalinaTmp"]
        self.tomcatServerTmp = self.confDict["tomcatServerTmp"]
        self.serverConf = self.confDict["serverConf"].format(envName=envName,)
        # 初始化基础目录
        if not os.path.exists(self.deploymentAppDir):
            os.makedirs(self.deploymentAppDir)
        if not os.path.exists(self.bakDir):
            os.makedirs(self.bakDir)
        if not os.path.exists(self.serverConf):
            print("serverconf is not exists,check serverconf %s " % self.serverConf)
            print(""" xkj-pay-api:
                        startNum: 20
                        buildDir: /project/project-build/pay-api-build
                        deployDir: /project/project-deploy/pay-api
                        targetDir: /project/project-build/pay-api-build/target/com.hmyun.h5.pay
                        svnUrl: svn://192.168.251.100/开发/RPC/API-PAY/V4.0.0/代码/com.hmyun.h5.pay-V4.0.0
                        giturl: ssh://git@gitlab.xkj.com:222/root/xkj-upload.git
                        testNodeName:
                            - test1
                        devNodeName:
                            - dev2
                        proNodeName:
                            - node1
                        war: /project/project-build/pay-api-build/target/com.hmyun.h5.pay.war
                        http_port: 9440
                        ajp_port: 9441
                        shutdown_port: 9442
                        xms: 512m
                        xmx: 512m""" % self.serverConf)
            sys.exit()
        else:
            # 读配置文件 服务配置
            self.serverNameDictList = readYml(self.serverConf)
            if not self.chekPort():
                sys.exit()

    def chekPort(self):
        portList = []
        for serverName, portDict in self.serverNameDictList.items():
            for portstr,port in portDict.items():
                if portstr =="startNum":
                    startNum = portDict["startNum"]
                    portList.append(startNum)
                    continue
                if not portstr.endswith("port"):
                    continue
                portList.append(portDict[portstr])
        for port, num in Counter(portList).items():
            if num > 1:
                print("%s is duplicated" % port)
                print("check conf port or startNum")
                return False
        return True

    def getDeploymentTomcatPath(self,serverName):
        dateTime = time.strftime('%Y-%m-%d')
        deployServerDir = os.path.join(self.deploymentAppDir, "%s%s") % (self.tomcatPrefix, serverName)
        deployServerWarDir = os.path.join(self.deploymentAppDir, "%s%s/%s") % (self.tomcatPrefix, serverName, "webapps/ROOT")
        deployServerWar = os.path.join(self.deploymentAppDir, "%s%s/%s") % (self.tomcatPrefix, serverName, "webapps/ROOT.war")
        deployServerTomcatDir = os.path.join(self.deploymentAppDir, "%s%s") % (self.tomcatPrefix, serverName)
        # deployServerXmlDir = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName,"conf/server.xml")
        deployServerXmlDir = os.path.join(self.deploymentAppDir, "%s%s/%s") % (self.tomcatPrefix, serverName, "conf/server.xml")
        deployServerLogsDir = os.path.join(self.deploymentAppDir, "%s%s/%s") % (self.tomcatPrefix, serverName, "logs/catalina.out")
        deployServerLogsDirBak = os.path.join(self.deploymentAppDir, "%s%s/%s--%s.log") % (
        self.tomcatPrefix, serverName, "logs/catalina.out", dateTime)
        # deployServerLogsDir = os.path.join(deploymentAppDir, "%s%s/%s-%s.log") % (tomcatPrefix, serverName, "logs/catalina.out",dateTime)
        bakServerDir = os.path.join(self.bakDir, "%s%s") % (self.tomcatPrefix, serverName)
        return {"deployServerDir": deployServerDir,
                "deployServerWarDir": deployServerWarDir,
                "deployServerTomcatDir": deployServerTomcatDir,
                "deployServerXmlDir": deployServerXmlDir,
                "bakServerDir": bakServerDir,
                "deployServerWar": deployServerWar,
                "deployServerLogsDir": deployServerLogsDir,
                "deployServerLogsDirBak": deployServerLogsDirBak
                }

    def checkServer(self,serverName):
        if os.path.exists(self.getDeploymentTomcatPath(serverName)["deployServerDir"]):
            return True
        else:
            return False

    def installServeTomact(self,serverName):
        if not os.path.exists(self.baseTomcat):
            print("Base tomcat File (%s) is not exists" % self.baseTomcat)
            sys.exit()
        serverList = []
        if not self.checkServer(serverName):
            for serName, optionsDict in self.serverNameDictList.items():
                serverList.append(serName)
            if serverName in serverList:
                if serverName in self.serverNameDictList:
                    optionsDict = self.serverNameDictList[serverName]
                    try:
                        shutdown_port = optionsDict["shutdown_port"]
                        http_port = optionsDict["http_port"]
                        ajp_port = optionsDict["ajp_port"]
                    except KeyError as e:
                        print("please check conf file with :%s" % e)
                    deployDir = self.getDeploymentTomcatPath(serverName)["deployServerDir"]  # 部署工程目录
                    # 从标准tomcat 复制到部署目录
                    # self.copyBaseTomcat(serverName)
                    copyDir(serverName,self.baseTomcat,deployDir)
                    # 修改部署tomcat server.xml配置文件
                    chownCmd = "chown -R tomcat:tomcat %s" % deployDir  # 目录权限修改
                    self.changeXML(serverName)
                    stdout, stderr = execShSmall(chownCmd)
                    if stdout:
                        print(stdout)
                    if stderr:
                        print(stderr)
                    print("%s install sucess" % serverName)
            else:
                print("serverName:%s is errr" % serverName)
        else:
            print("%s is installed" % serverName)

    def installServerType(self, serverName,buildType):
        # serverNameDict = projectDict[serverName]
        deployDir= self.serverNameDictList[serverName]["deployDir"]
        # print projectDict
        if buildType == "jar" or buildType == "tomcat":
            usergroup = "tomcat"
            user = "tomcat"
        else:
            usergroup = "node"
            user = "node"
        if os.path.exists(deployDir):
            if dir_is_null(deployDir):
                chownCmd = "chown -R {usergroup}:{user} {deployDir}".format(usergroup=usergroup,user=user,deployDir=deployDir)  # 目录权限修改
                stdout, stderr = execShSmall(chownCmd)
                if stdout:
                    print(stdout)
                if stderr:
                    print(stderr)
                print("%s 安装成功" % serverName)
                return True
            else:
                print("%s 已经安装，请检查!" % serverName)
                return False
        else:
            # os.mkdirs(deployDir)
            os.makedirs(deployDir)
            chownCmd = "chown -R {usergroup}:{user} {deployDir}".format(usergroup=usergroup,user=user,deployDir=deployDir)   # 目录权限修改
            stdout, stderr = execShSmall(chownCmd)
            if stdout:
                print(stdout)
            if stderr:
                print(stderr)
            print("%s 安装成功" % serverName)
            return True

    def installServer(self,serverName):
        buildType = self.serverNameDictList[serverName]["buildType"]
        if buildType == "tomcat":
            self.installServeTomact(serverName)
            self.changeCatalina(serverName)
        else:
            self.installServerType(serverName,buildType)

    def changeCatalina(self,serverName):
        dicttmp = {}
        if serverName == "xkj-job-admin":
            return
        """修改tocmat 启动内存参数，批量部署根据每个服务名的设置，调整完需要重启服务。"""
        if not self.checkServer(serverName):
            print("%s is not install" % serverName)
        deployDir = self.getDeploymentTomcatPath(serverName)["deployServerDir"]  # 部署工程目录
        serverNameDict = self.serverNameDictList[serverName]
        xms = serverNameDict['xms']
        xmx = serverNameDict['xmx']
        jmxport = serverNameDict['jmx_port']
        ip = getip()
        initCatalinaPathTMP = os.path.join(self.baseTomcat, "bin/catalina.sh.tmp")
        CatalinaPathTMP = os.path.join(deployDir, "bin/catalina.sh.tmp")
        # 更新模板文件
        copyFile(serverName,initCatalinaPathTMP, CatalinaPathTMP)
        if not os.path.exists(CatalinaPathTMP):
            print("%s is not exixst need reinstall" % serverName)
            sys.exit(1)
        CatalinaPath = os.path.join(deployDir, "bin/catalina.sh")
        CatalinaPathBak = os.path.join(deployDir, "bin/catalina.sh.bak")

        if os.path.exists(CatalinaPath):
            # 备份原启动文件
            if not os.path.exists(CatalinaPathBak):
                shutil.copyfile(CatalinaPath, CatalinaPathBak)
        dicttmp["ip"] = ip
        dicttmp["catalinahome"] = deployDir
        dicttmp["xms"] = xms
        dicttmp["xmx"] = xmx
        dicttmp["jmxport"] = jmxport
        dicttmp["pinpointid"] = serverName
        dw = xmx[-1]
        n = int(xmx[0:-1])
        xmn = str(int(n / 2)) + dw
        dicttmp["xmn"] = xmn
        genTmpFile(serverName, dicttmp, CatalinaPathTMP, CatalinaPath)

    def changeXML(self,serverName):
        """修改tocmat 启动服务参数，批量部署根据每个服务名的设置，调整完需要重启服务。"""
        if not self.checkServer(serverName):
            print("%s is not install" % serverName)
        deployDir = self.getDeploymentTomcatPath(serverName)["deployServerDir"]  # 部署工程目录
        deployServerWarDir = self.getDeploymentTomcatPath(serverName)["deployServerWarDir"]  # 部署工程目录
        serverNameDict = self.serverNameDictList[serverName]
        shutdown_port = serverNameDict["shutdown_port"]
        http_port = serverNameDict["http_port"]
        warDir = deployServerWarDir
        ajp_port = serverNameDict["ajp_port"]
        initCatalinaPathTMP = os.path.join(self.baseTomcat, "conf/server.xml")
        CatalinaPathTMP = os.path.join(deployDir, "conf/server.xml")
        if not os.path.exists(CatalinaPathTMP):
            print("%s is not exixst need reinstall" % serverName)
            sys.exit(1)
        CatalinaPath = os.path.join(deployDir, "conf/server.xml")
        CatalinaPathBak = os.path.join(deployDir, "conf/server.xml.bak")
        if os.path.exists(CatalinaPath):
            # 备份原启动文件
            if not os.path.exists(CatalinaPathBak):
                shutil.copyfile(CatalinaPath, CatalinaPathBak)
            # 更新模板文件
        copyFile(serverName,initCatalinaPathTMP, CatalinaPathTMP)
        dicttmp = {}
        dicttmp["warDir"] = warDir
        dicttmp["http_port"] = http_port
        dicttmp["shutdown_port"] = shutdown_port
        dicttmp["serverName"] = serverName
        genTmpFile(serverName, dicttmp, CatalinaPathTMP, CatalinaPath)

    def changeXml(self,serverName, shutdown_port="8128", http_port="8083", ajp_port="8091"):
        ## xml 设置模板，废弃，通过genTmpFile模板化生成文件
        deployPath = self.getDeploymentTomcatPath(serverName)
        warDir = deployPath["deployServerWarDir"]  # 解压的war 目录
        xmlpath = deployPath["deployServerXmlDir"]
        print("修改服务:%s,配置文件:%s" % (serverName,xmlpath))
        dicttmp={}
        dicttmp["warDir"]=warDir
        dicttmp["http_port"]=http_port
        dicttmp["shutdown_port"]=shutdown_port
        dicttmp["serverName"]=serverName
        domtree = xml.dom.minidom.parse(xmlpath)
        collection = domtree.documentElement
        service = collection.getElementsByTagName("Service")
        collection.setAttribute("port", str(shutdown_port))  # shutdown port
        context = collection.getElementsByTagName("Context")  # 设置网站目录
        context[0].setAttribute("docBase", warDir)
        if serverName == "xkj-upload":
            "设置工程支持软连接"
            context[0].setAttribute("allowLinking", "true")
        for i in service:
            connector = i.getElementsByTagName("Connector")
            Executor = i.getElementsByTagName("Executor")
            Executor[0].setAttribute("name", serverName + "-tomcatThreadPool")
            appdeploy = i.getElementsByTagName("Host")
            appdeploy[0].setAttribute("appBase", "webapps")  # 部署目录 默认为webapps
            connector[0].setAttribute("port", str(http_port))  # http port
            connector[0].setAttribute("executor", serverName + "-tomcatThreadPool")  # http port
            # connector[1].setAttribute("port", str(ajp_port))  # ajp port
        # outfile = File(xmlpath, 'w')
        outfile = open(xmlpath,'wb')
        write = codecs.lookup("utf-8")[3](outfile)
        domtree.writexml(write, addindent=" ", encoding='utf-8')
        write.close()

    def uninstallServer(self,serverName):
        # serverNameDictList = readConf(serverConfPath)
        if self.checkServer(serverName):
            # for serverNameDict in serverNameDictList:
            deployDir = self.getDeploymentTomcatPath(serverName)["deployServerDir"]
            # deployServerDir()
            if serverName in self.serverNameDictList:
                self.stopServer(serverName)
                cleanDir(deployDir)
                print("%s is uninstall sucess!" % serverName)
        else:
            print("%s is not instell or is err" % serverName)

    def getPid(self,serverName):
        deployDir = self.getDeploymentTomcatPath(serverName)["deployServerDir"]
        serverNameDict = self.serverNameDictList[serverName]
        jar = serverNameDict["deployFile"]
        jarName = jar.split("/")[-1]
        deployjar = os.path.join(deployDir, jarName)
        # cmd = "pgrep -f %s" % servername
        """处理在打开部署目录下文件的情况下进行部署操作会无法准确获取pid"""
        typeName = serverNameDict["buildType"]
        if typeName == "jar":
            cmd = "pgrep -f %s" % deployjar
        else:
            cmd = "pgrep -f %s/temp" % deployDir
        pid, stderr = execShSmall(cmd)
        if pid:
            # string(pid,)
            # pidlist = [int(i.strip()) for i in pid.split(str.encode("\n")) if i]
            pidlist = [i.strip() for i in pid.split("\n") if i]
            print("%s is started" % serverName)
            print("Get PID:{pid}".format(pid=pidlist))
            return pidlist
        else:
            print("%s is stoped" % serverName)

    def stopServer(self,serverName):
        # 停止服务 先正常停止，多次检查后 强制杀死！
        deployDir = self.getDeploymentTomcatPath(serverName)["deployServerTomcatDir"]
        shutdown = os.path.join(deployDir, "bin/shutdown.sh")
        cmd = "sudo su - tomcat -c '/bin/bash %s'" % shutdown
        pid = self.getPid(serverName)
        serverNameDict = self.serverNameDictList[serverName]
        typeName = serverNameDict["buildType"]
        if typeName == "jar":
            if not pid:
                print("Server:%s is down" % serverName)
                return True
            for p in pid:
                cmd = "sudo kill -9 %s" % str(p)

        if not pid:
            print("Server:%s is down" % serverName)
            return True
        else:
            stdout, stderr = execShSmall(cmd)  # 执行 shutdown命令
            if stdout:
                print("stdout:%s" % stdout)
            if stderr:
                print("stderr:%s " % stderr)
            for i in range(self.checktime):
                time.sleep(3)
                print("check servname :%s num:%s" % (serverName, i + 1))
                if not self.getPid(serverName):
                    print("Server:%s,shutdown success" % serverName)
                    return True
        pid_TMP = self.getPid(serverName)
        if pid_TMP:
            print("Server:%s,shutdown fail pid:%s" % (serverName, pid_TMP))
            try:
                for p in pid:
                    cmd = "sudo kill -9 %s" % p
                    killstdout, killsterr = execShSmall(cmd)
                    if killstdout:
                        print(killstdout)
                    if killsterr:
                        print(killsterr)
                    # os.kill(pid, signal.SIGKILL)
                    # os.kill(pid, signal.9) #　与上等效
                    print('Killed server:%s, pid:%s' % (serverName, pid_TMP))
            except OSError as e:
                print('No such as server!', e)
            if self.getPid(serverName):
                print("shutdown fail,check server:%s" % serverName)
                return False
        else:
            print("Server:%s,shutdown success" % serverName)
            return True

    def startServer(self,serverName):
        now = datetime.datetime.now()
        data_time = now.strftime('%Y-%m-%d')
        serverNameDict = serverNameDictList[serverName]
        typeName = serverNameDict["buildType"]
        deploydir = serverNameDict["deployDir"]
        jar = serverNameDict["deployFile"]
        jarName = jar.split("/")[-1]
        deployjar = os.path.join(deploydir, jarName)
        deployDir = self.getDeploymentTomcatPath(serverName)["deployServerTomcatDir"]
        serverlogpath = os.path.join(self.logsPath, "%s-%s.log") % (serverName, data_time)
        xms = serverNameDict["xms"]
        xmx = serverNameDict["xmx"]
        jmxport = serverNameDict['jmx_port']
        # ip = confDict[]
        startSh = os.path.join(deployDir, "bin/startup.sh")
        if typeName == "jar":
            rootJar = os.path.join(deploydir, "ROOT.jar")
            if os.path.exists(rootJar):
                cleanDir(deployjar)
                print("重命名%s 》》 %s" % (rootJar, deployjar))
            # if os.path.exists(deployjar):

                os.rename(rootJar, deployjar)

            if envName == "dev":
                deploynode = serverNameDict["devNodeName"][0]
            if envName == "test":
                deploynode = serverNameDict["testNodeName"][0]
            if envName == "pro":
                deploynode = serverNameDict["proNodeName"][0]
            # ip = self.hostDict[deploynode]
            ip = getip()
            cmd = """sudo su - tomcat -c '%s %s -Xms%s -Xmx%s \
                    -Dcom.sun.management.jmxremote.port=%s \
                    -Dcom.sun.management.jmxremote.authenticate=false \
                    -Djava.rmi.server.hostname=%s \
                    -Dcom.sun.management.jmxremote.ssl=false -jar %s >%s 2>&1 &'""" % (
            self.nohup, self.java, xms, xmx, jmxport, ip, deployjar, serverlogpath)
        else:
            cmd = "sudo su - tomcat -c '/bin/bash %s'" % startSh
        binDir = os.path.join(deployDir, "bin/*")
        deployServerWarDir = self.getDeploymentTomcatPath(serverName)["deployServerWarDir"]

        pid = self.getPid(serverName)
        if not pid:
            # 每次启动重新命名catalina 防止一直增长
            # 使用lograted 配置
            # reNameCatalina(serverName)
            print("Start Server:%s" % (serverName))
            stdout, stderr = execShSmall(cmd)  # 执行 启动服务命令
            if stdout:
                print("stdout:%s" % stdout)
            if stderr:
                print("stderr:%s " % stderr)
            for i in range(self.checktime):
                # time.sleep(5)
                print("check servname :%s num:%s" % (serverName, i + 1))
                pidtmp = self.getPid(serverName)
                if typeName == "jar":
                    print("Server:%s,start success pid:%s" % (serverName, pidtmp))
                    return True
                else:
                    res = self.checkStartSucss(serverName)
                    if pidtmp and res:
                        print("Server:%s,start success pid:%s" % (serverName, pidtmp))
                        return True
            pidtmp = self.getPid(serverName)
            if typeName == "jar":
                res = True
            else:
                res = self.checkStartSucss(serverName)
            if self.getPid(serverName) and res:
                print("Server:%s,Sucess pid:%s" % (serverName, pidtmp))
                return True
            else:
                print("Server:%s,is not running" % serverName)
                return False
        else:
            pidtmp = self.getPid(serverName)
            print("Server:%s,Sucessed pid:%s" % (serverName, pid))
            return True

    def checkStartSucss(self,serverName):
        serverDict = self.getDeploymentTomcatPath(serverName)
        deployServerLogsDir = serverDict["deployServerLogsDir"]
        cmd = "tail -F %s" % deployServerLogsDir
        print(cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        num = 1
        while True:
            for line in iter(p.stdout.readline, ''):
                num += 1
                print(str(line.rstrip(), encoding='utf-8'))
                if b"Server startup in" in line:
                    print("check server started Success")
                    return True
                if num >= 200:
                    print("check server started False")
                    return False
            print("check server started status line num: %s" % num)
            p.wait()

    def rollBack(self,serverName, version=-1):
        dirDict = self.getDeploymentTomcatPath(serverName)
        versionList = self.getVersion(serverName)
        print(versionList)
        serverNameDict = self.serverNameDictList[serverName]
        typeName = serverNameDict["buildType"]
        if typeName == "jar":
            serverNameDict = self.serverNameDictList[serverName]
            deploydir = serverNameDict["deployDir"]
            jar = serverNameDict["deployFile"]
            jarName = jar.split("/")[-1]
            deployWar = os.path.join(deploydir, jarName)

        if not versionList:
            print("Not Back war File :%s" % serverName)
        else:
            if not version:
                versionId = versionList[-1]
            else:
                versionId = versionList[int(version)]
            if typeName == "jar":
                bakdeployWar = os.path.join(dirDict["bakServerDir"], "jar.%s") % (versionId)
                deployRootWar = dirDict["deployServerWarDir"]
                deployServerWar = os.path.join(deploydir, jarName)
            else:
                bakdeployWar = os.path.join(dirDict["bakServerDir"], "war.%s") % (versionId)
                deployRootWar = dirDict["deployServerWarDir"]
                deployServerWar = dirDict["deployServerWar"]
                if typeName == "node":
                    deployServerWar = serverNameDict["deployDir"]
            if os.path.exists(deployServerWar):
                cleanDir(deployServerWar)
            if os.path.exists(deployRootWar):
                cleanDir(deployRootWar)
            # copyDir(bakdeployWar, deployRootWar)
            if typeName == "node":
                copyDir(serverName,bakdeployWar, deployServerWar)
            else:
                copyFile(serverName,bakdeployWar, deployServerWar)
                chownCmd = "chown -R tomcat:tomcat %s" % deployServerWar  # 目录权限修改
                stdout, stderr = execShSmall(chownCmd)
                if stdout:
                    print(stdout)
                if stderr:
                    print(stderr)
            if os.path.exists(deployServerWar):
                print("RollBack Sucess,update serverName:%s" % serverName)
                print("Rollback Version:%s " % versionId)
            else:
                print("check File:%s ,rollback Faile" % deployServerWar)

    def cleanROOT(self,serverName):

        deployServerWarDir = self.getDeploymentTomcatPath(serverName)["deployServerWarDir"]
        cleanDir(deployServerWarDir)
        return True

    def cleanRootTomcat(self,serverName, action):
        deployServerWarDir = self.getDeploymentTomcatPath(serverName)["deployServerWarDir"]
        deployWar = self.getDeploymentTomcatPath(serverName)["deployServerWar"]
        if action == "delwar":
            cleanDir(deployWar)
            return True
        elif action == "delroot":
            cleanDir(deployServerWarDir)
            return True
        else:
            pass

    def backWar(self,serverName):
        serverNameDict = self.serverNameDictList[serverName]
        typeName = serverNameDict["buildType"]
        if typeName == "jar":
            # serverNameDict = serverNameDictList[serverName]
            deploydir = serverNameDict["deployDir"]
            jar = serverNameDict["deployFile"]
            jarName = jar.split("/")[-1]
            deployWar = os.path.join(deploydir, jarName)
        elif typeName =="node":
            deployWar = serverNameDict["deployDir"]
        else:
            # 部署的war包
            deployWar = self.getDeploymentTomcatPath(serverName)["deployServerWar"]
        # 备份war包路径
        bakServerDir = self.getDeploymentTomcatPath(serverName)["bakServerDir"]
        if not os.path.exists(bakServerDir):
            os.mkdir(bakServerDir)
        versionId = self.getBackVersionId(serverName)  # 同一日期下的最新版本
        try:
            lastVersinId = self.getVersion(serverName)[-1]
        except:
            # 获取 备份文件列表 如果没有备份 返回备份起始版本1
            lastVersinId = [time.strftime("%Y-%m-%d-") + "V1"][-1]
            # print lastVersinId
        if typeName == "jar":
            bakdeployRootWar = os.path.join(bakServerDir, "jar.%sV%s") % (time.strftime("%Y-%m-%d-"), versionId)
            lastbakdeployRootWar = os.path.join(bakServerDir, "jar.%s") % (lastVersinId)
        else:
            bakdeployRootWar = os.path.join(bakServerDir, "war.%sV%s") % (time.strftime("%Y-%m-%d-"), versionId)
            lastbakdeployRootWar = os.path.join(bakServerDir, "war.%s") % (lastVersinId)

        if not self.checkServer(serverName):
            print("%s is not install" % serverName)
        else:
            if os.path.exists(deployWar):
                if not os.path.exists(lastbakdeployRootWar):
                    print("back %s >>> %s" % (deployWar, bakdeployRootWar))
                    if os.path.isdir(deployWar):
                        copyDir(serverName,deployWar, bakdeployRootWar)
                    else:
                        copyFile(serverName,deployWar, bakdeployRootWar)
                    # copyDir(deployWar, bakdeployRootWar)
                else:
                    # 判断 最后一次备份和现在的文件是否 修改不一致，如果一致就不备份，
                    if not getTimeStamp(deployWar) == getTimeStamp(lastbakdeployRootWar):
                        print("back %s >>> %s" % (deployWar, bakdeployRootWar))
                        # copyDir(deployWar, bakdeployRootWar)
                        if os.path.isdir(deployWar):
                            copyDir(serverName, deployWar, bakdeployRootWar)
                        else:
                            copyFile(serverName, deployWar, bakdeployRootWar)
                        self.cleanHistoryBak(serverName)
                        if os.path.exists(bakdeployRootWar):
                            print("back %s sucess" % bakdeployRootWar)
                        else:
                            print("back %s fail" % deployWar)
                    else:
                        # print getVersion(serverName)
                        print("File:%s is not modify,not need back" % deployWar)
            else:
                print("file %s or %s is not exists" % (deployWar, bakdeployRootWar))


    # 清理历史多余的备份文件和原来的war包
    def cleanHistoryBak(self,serverName):
        bakServerDir = self.getDeploymentTomcatPath(serverName)["bakServerDir"]
        VersinIdList = self.getVersion(serverName)
        if VersinIdList:
            if len(VersinIdList) > int(self.bakNum):
                cleanVersionList = VersinIdList[0:abs(len(VersinIdList) - int(bakNum))]
                for i in cleanVersionList:
                    bakWarPath = os.path.join(bakServerDir, "war.%s") % i
                    cleanDir(bakWarPath)
            else:
                pass
        else:
            print("%s is not bak War" % serverName)

    def versionSort(self,list):
        # 对版本号排序 控制版本的数量
        from distutils.version import LooseVersion
        vs = [LooseVersion(i) for i in list]
        vs.sort()
        return [i.vstring for i in vs]

    def getBackVersionId(self,serverName):
        date = time.strftime("%Y-%m-%d")
        versionIdList = self.getVersion(serverName)
        if not versionIdList:
            return 1
        else:
            # 同一日期下的最新版本+1
            if date != self.versionSort(versionIdList)[-1].split("-V")[0]:
                return 1
            else:
                return int(versionIdList[-1].split("-")[-1].split("V")[-1]) + int(1)

    def getVersion(self,serverName):
        bakdeployRoot = self.getDeploymentTomcatPath(serverName)["bakServerDir"]
        serverNameDict = self.serverNameDictList[serverName]
        typeName = serverNameDict["buildType"]
        versionIdList = []
        try:
            for i in os.listdir(bakdeployRoot):
                # print i
                if typeName == "jar":
                    if i.split(".")[0] == "jar":
                        versionId = i.split(".")[1]
                        versionIdList.append(versionId)
                else:
                    if i.split(".")[0] == "war":
                        versionId = i.split(".")[1]
                        versionIdList.append(versionId)
        except:
            return []
        if not versionIdList:
            return []
        return self.versionSort(versionIdList)  # 返回版本号升序列表

def main(action,serverName,version,envName):
    serverconf = "/silencedeploy/config/config.yaml"
    agenet = deployAgent(serverconf,envName)
    action = action.lower()
    if action =="install":
        agenet.installServer(serverName)
    elif action == "uninstall":
        agenet.uninstallServer(serverName)
    elif action == "stop":
        agenet.stopServer(serverName)
    elif action == "start":
        agenet.startServer(serverName)
    elif action == "restart":
        agenet.stopServer(serverName)
        agenet.startServer(serverName)
    elif action == "reinstall":
        agenet.uninstallServer(serverName)
        agenet.installServer(serverName)
    elif action == "back":
        agenet.backWar(serverName)
    elif action == "cleanroot":
        agenet.cleanROOT(serverName)
    elif action == "delroot":
        agenet.cleanRootTomcat(serverName,action)
    elif action == "delwar":
        agenet.cleanRootTomcat(serverName, action)
    elif action == "changmen":
        agenet.changeCatalina(serverName)
    elif action == "changxml":
        agenet.changeXML(serverName)
        # cleanROOT(serverName)
    elif action == "status":
        if not agenet.getPid(serverName):
            print("%s is stoped" % serverName)
        else:
            print("%s is started" % serverName)
    elif action == "rollback":
        agenet.stopServer(serverName)
        agenet.rollBack(serverName, version)
        if agenet.serverNameDictList[serverName]["buildType"] != "node":
            agenet.startServer(serverName)
    elif action == "getback":
        versionlist = agenet.getVersion(serverName)
        if not versionlist:
            print("%s not back" % serverName)
        else:
            print("%s has back version:%s" % (serverName, versionlist))
    else:
        print("action is -a 111 [deploy,install,uninstall,reinstall,stop,start,restart,back,rollback,getback] -n servername [all]")
        print("action:(%s)" % action)
        print("env:%s" % envName)
        sys.exit(1)

if __name__ == "__main__":

    options, args = getOptions()
    action = options.action
    version = options.versionId
    serverName = options.serverName
    envName = options.envName
    serverConf = "/silencedeploy/config/startService-normal-{envName}.yaml".format(envName=envName)
    serverNameDictList=readYml(serverConf)
    if serverName == "all":
        for serverNameDict in serverNameDictList:
            for seName, portDict in serverNameDict.iteritems():
                main(action, seName, version, envName)
    else:
       main(action, serverName, version, envName)

