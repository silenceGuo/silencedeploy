#!/usr/bin/env python
# -*-coding:utf-8-*-
# @Author : gzq
# @date   : 2018/1/10 0010 16:30
# @file   : deploy-liunx.py
# 该脚本部署在统一的目录下通过，实现本地及远程服务器上的服务部署，重启，发布,分发,回滚等操作
# 登陆远程服务器需提前配置好ssh密钥登陆
from subprocess import PIPE, Popen
import datetime
import os
import sys
import xml.dom.minidom
from tornado import template
import signal
import codecs
import logging
import shutil
from logging import handlers
import zipfile
import time
import yaml
from optparse import OptionParser
reload(sys)
sys.setdefaultencoding('utf-8')

def getOptions():
    parser = OptionParser()

    parser.add_option("-n", "--serverName", action="store",
                      dest="serverName",
                      default=False,
                      help="serverName to do")
    parser.add_option("-a", "--action", action="store",
                      dest="action",
                      default=False,
                      help="action -a [deploy,install,uninstall,reinstall,stop,start,restart,back,rollback,getback]")
    parser.add_option("-v", "--versionId", action="store",
                      dest="versionId",
                      default=False,
                      help="-v versionId")
    parser.add_option("-e", "--envName", action="store",
                      dest="envName",
                      default=False,
                      help="-e envName")
    parser.add_option("-t", "--typeName", action="store",
                      dest="typeName",
                      default=False,
                      help="-t typeName")
    options, args = parser.parse_args()
    return options, args

def getDeploymentTomcatPath(serverName):
    dateTime = time.strftime('%Y-%m-%d')
    deployServerDir = os.path.join(deploymentAppDir, "%s%s") % (tomcatPrefix, serverName)
    deployServerWarDir = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName, "webapps/ROOT")
    deployServerWar = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName, "webapps/ROOT.war")
    deployServerTomcatDir = os.path.join(deploymentAppDir, "%s%s") % (tomcatPrefix, serverName)
    # deployServerXmlDir = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName,"conf/server.xml")
    deployServerXmlDir = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName,"conf/server.xml")
    deployServerLogsDir = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName,"logs/catalina.out")
    deployServerLogsDirBak = os.path.join(deploymentAppDir, "%s%s/%s--%s.log") % (tomcatPrefix, serverName,"logs/catalina.out",dateTime)
    # deployServerLogsDir = os.path.join(deploymentAppDir, "%s%s/%s-%s.log") % (tomcatPrefix, serverName, "logs/catalina.out",dateTime)
    bakServerDir = os.path.join(bakDir, "%s%s") % (tomcatPrefix, serverName)
    return {"deployServerDir":deployServerDir,
            "deployServerWarDir":deployServerWarDir,
            "deployServerTomcatDir":deployServerTomcatDir,
            "deployServerXmlDir":deployServerXmlDir,
            "bakServerDir": bakServerDir,
            "deployServerWar": deployServerWar,
            "deployServerLogsDir":deployServerLogsDir,
            "deployServerLogsDirBak":deployServerLogsDirBak
            }

def _init(confPath):
    # 初始化基础目录
    if not os.path.exists(deploymentAppDir):
        os.makedirs(deploymentAppDir)
    if not os.path.exists(bakDir):
        os.makedirs(bakDir)
    if not os.path.exists(confPath):
        print "serverconf is not exists,check serverconf %s "% confPath
        print """ xkj-pay-api:
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
                    xmx: 512m""" % confPath
        sys.exit()
    else:
        # 读配置文件 服务配置
        global serverNameDictList
        serverNameDictList = readYml(confPath)
        # print serverNameDictList
        if not chekPort():
            sys.exit()

def getDir(dir):
    l1 = []
    for (root, dirs, files) in os.walk(dir, False):
        for filename in files:
            abs_path = os.path.join(root, filename)
            l1.append(abs_path)
    return l1

def readYml(file):
    with open(file)as fd:
       res = yaml.safe_load(fd)
    return res

# 检查服务注册状态
def checkServer(serverName):

    if os.path.exists(getDeploymentTomcatPath(serverName)["deployServerDir"]):
        # print "%s is installed" % serverName
        return True
    else:
        # print "%s is not install" % serverName
        return False

# 检查端口占用
def chekPort():
    from collections import Counter
    portList=[]
    # for serverNameDict in serverNameDictList:
    for serverName, portDict in serverNameDictList.iteritems():
            # print(portDict)
            shutdown_port = portDict["shutdown_port"]
            http_port = portDict["http_port"]
            ajp_port = portDict["ajp_port"]
            startNum = portDict["startNum"]
            jmxport = portDict["jmx_port"]
            portList.append(startNum)
            portList.append(http_port)
            portList.append(jmxport)
            portList.append(shutdown_port)
            portList.append(ajp_port)

    for port, num in Counter(portList).iteritems():
        if num > 1:
            print "%s is duplicated" % port
            print "check conf port or startNum"
            return False
    return True


# 注册服务
def installServer(serverName):
    if not os.path.exists(baseTomcat):
        print "Base tomcat File (%s) is not exists" % baseTomcat
        sys.exit()

    serverList = []
    if not checkServer(serverName):
        # for serverNameDict in serverNameDictList:
        for serName, optionsDict in serverNameDictList.iteritems():
                serverList.append(serName)
       # print serverList
        if serverName in serverList:
            # for serverNameDict in serverNameDictList:
                if serverNameDictList.has_key(serverName):
                    optionsDict = serverNameDictList[serverName]
                    try:
                        shutdown_port = optionsDict["shutdown_port"]
                        http_port = optionsDict["http_port"]
                        ajp_port = optionsDict["ajp_port"]
                    except KeyError, e:
                        # print e
                        print "please check conf file with :%s" % e
                        # continue
                        #sys.exit(1)
                    deployDir = getDeploymentTomcatPath(serverName)["deployServerDir"]  # 部署工程目录
                    print deployDir
                    # sys.exit()
                    # 从标准tomcat 复制到部署目录
                    copyBaseTomcat(serverName)
                    # 修改部署tomcat server.xml配置文件
                    chownCmd = "chown -R tomcat:tomcat %s" % deployDir  # 目录权限修改
                    changeXml(serverName, shutdown_port=shutdown_port, http_port=http_port, ajp_port=ajp_port)
                    stdout, stderr = execSh(chownCmd)
                    if stdout:
                        print stdout
                    if stderr:
                        print stderr
                    print"%s install sucess" % serverName
                    # break
        else:
            print "serverName:%s is errr" %serverName
    else:
        print "%s is installed" % serverName


def genConfigString(configtemplate, configvalues):
    loader = template.Loader(configtemplate)
    ret = loader.load(configtemplate).generate(**configvalues)
    return ret

def genConfigFile(serverName,dicttmp):
    deployDir = getDeploymentTomcatPath(serverName)["deployServerDir"]  # 部署工程目录
    initCatalinaPathTMP = os.path.join(baseTomcat, "bin/catalina.sh.tmp")
    CatalinaPath = os.path.join(deployDir, "bin/catalina.sh")
    print "生成%s ,配置文件;%s" % (serverName, CatalinaPath)
    configstring = genConfigString(initCatalinaPathTMP, dicttmp)
    print(configstring[0:1050])
    fp_config = open(CatalinaPath, 'w')
    fp_config.write(configstring)
    fp_config.close()

def getip():
    stdout ,stderr = execSh("ip a")
    ipstr = [i.strip() for i in stdout.split("\n") if i.strip().startswith("inet 192.168.")]
    print ipstr
    for i in ipstr:
        if "eth" in i or "eno" in i:
            iplist = i.split(" ")
            # print iplist
            for ips in iplist:
                if ips.startswith("192.168.") and not ips.endswith("255"):
                    ip = ips.split("/")[0]
    if ip:
        print("获取节点ip：%s" % ip)
        return ip
    else:
        print("未获取节点ip 请检查" )
        return "192.168.0.2"
def changeCatalina(serverName):
    dicttmp = {}
    if serverName == "xkj-job-admin":
        return
    """修改tocmat 启动内存参数，批量部署根据每个服务名的设置，调整完需要重启服务。"""
    if not checkServer(serverName):
        print "%s is not install" % serverName
    deployDir = getDeploymentTomcatPath(serverName)["deployServerDir"]  # 部署工程目录
    serverNameDict = serverNameDictList[serverName]
    xms = serverNameDict['xms']
    xmx = serverNameDict['xmx']
    jmxport = serverNameDict['jmx_port']
    ip = getip()
    initCatalinaPathTMP = os.path.join(baseTomcat,"bin/catalina.sh.tmp")
    CatalinaPathTMP = os.path.join(deployDir, "bin/catalina.sh.tmp")
    # 更新模板文件
    copyFile(initCatalinaPathTMP, CatalinaPathTMP)
    if not os.path.exists(CatalinaPathTMP):
        # print CatalinaPathTMP
        print "%s is not exixst need reinstall" % serverName
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
    dw = xmx[-1]
    n = int(xmx[0:-1])
    xmn = str(int(n/2)) + dw
    dicttmp["xmn"] = xmn
    genConfigFile(serverName,dicttmp)
    # with open(CatalinaPathTMP) as fd:
    #     soure = fd.readlines()
    #     tmp = soure[1].format(xms=xms, xmx=xmx,jmxport=jmxport,ip=ip,catalinahome=deployDir)
    #     soure[1] = tmp
    #     print "调整启动内存参数为%s" % tmp
    #     with open(CatalinaPath, 'w+') as fd1:
    #         for line in soure:
    #             fd1.write(line)

def changeXML(serverName):
    """修改tocmat 启动服务参数，批量部署根据每个服务名的设置，调整完需要重启服务。"""
    if not checkServer(serverName):
        print "%s is not install" % serverName
    deployDir = getDeploymentTomcatPath(serverName)["deployServerDir"]  # 部署工程目录
    serverNameDict = serverNameDictList[serverName]
    shutdown_port = serverNameDict["shutdown_port"]
    http_port = serverNameDict["http_port"]
    ajp_port = serverNameDict["ajp_port"]
    initCatalinaPathTMP = os.path.join(baseTomcat,"conf/server.xml")
    CatalinaPathTMP = os.path.join(deployDir, "conf/server.xml")
    if not os.path.exists(CatalinaPathTMP):
        print CatalinaPathTMP
        print "%s is not exixst need reinstall" % serverName
        sys.exit(1)
    CatalinaPath = os.path.join(deployDir, "conf/server.xml")
    CatalinaPathBak = os.path.join(deployDir, "conf/server.xml.bak")

    if os.path.exists(CatalinaPath):
        # 备份原启动文件
        if not os.path.exists(CatalinaPathBak):
             shutil.copyfile(CatalinaPath, CatalinaPathBak)
        # 更新模板文件
    copyFile(initCatalinaPathTMP, CatalinaPathTMP)
    changeXml(serverName, shutdown_port=shutdown_port, http_port=http_port, ajp_port=ajp_port)

def uninstallServer(serverName):
    # serverNameDictList = readConf(serverConfPath)
    if checkServer(serverName):
        # for serverNameDict in serverNameDictList:
            if serverNameDictList.has_key(serverName):
                stopServer(serverName)
                cleanDeployDir(serverName)
                print "%s is uninstall sucess!" % serverName

    else:
        print "%s is not instell or is err" % serverName

def getPid(serverName):
    deployDir = getDeploymentTomcatPath(serverName)["deployServerDir"]
    serverNameDict = serverNameDictList[serverName]
    jar = serverNameDict["war"]
    jarName = jar.split("/")[-1]
    deployjar = os.path.join(deployDir, jarName)
    #cmd = "pgrep -f %s" % servername
    """处理在打开部署目录下文件的情况下进行部署操作会无法准确获取pid"""
    if typeName == "jar":
        cmd = "pgrep -f %s" % deployjar
        # myloger(serverName,msg="执行 pgrep -f %s" % deployjar)
    else:
        cmd = "pgrep -f %s/temp" % deployDir
        # cmd = "pgrep -f rancher"
        # cmd = "pgrep -f /metrics-server"
        # myloger(serverName, msg="执行 pgrep -f %s/tmp" % deployDir)
    pid, stderr = execSh(cmd)
    if pid:
        #string(pid,)
        pidlist = [i.strip() for i in pid.split("\n") if i]
        print "%s is started" % serverName
        print "Get PID:{pid}".format(pid=pidlist)
        return pidlist
        # myloger(serverName,msg="Get PID:{pid}".format(pid=pid))
    else:
        print "%s is stoped" % serverName

#方案二获取pid 不过只能针对centos7 且需要字符串处理过滤
"""ss -antp|grep 9120"""
"""LISTEN     0      100         :::9120                    :::*                   users:(("java",pid=99309,fd=46))"""

def stopServer(serverName):
    # 停止服务 先正常停止，多次检查后 强制杀死！
    deployDir = getDeploymentTomcatPath(serverName)["deployServerTomcatDir"]
    shutdown = os.path.join(deployDir, "bin/shutdown.sh")
    cmd = "sudo su - tomcat -c '/bin/bash %s'" % shutdown
    pid = getPid(serverName)
    if typeName == "jar":
        for p in pid:
            cmd = "sudo kill -9 %s" % p
    if not pid:
        print "Server:%s is down" % serverName
        return True
    else:
        stdout, stderr = execSh(cmd)  # 执行 shutdown命令
        if stdout:
            print "stdout:%s" % stdout
        if stderr:
            print "stderr:%s " % stderr

        for i in range(checktime):
            time.sleep(3)
            print "check servname :%s num:%s" % (serverName, i + 1)
            if not getPid(serverName):
                print "Server:%s,shutdown success" % serverName
                # myloger(serverName,msg="Server:%s,shutdown success " % serverName)
                return True
    pid_TMP = getPid(serverName)
    if pid_TMP:
        print "Server:%s,shutdown fail pid:%s" % (serverName, pid_TMP)
        try:
            for p in pid:
                cmd = "sudo kill -9 %s" % p
                killstdout, killsterr = execSh(cmd)
                if killstdout:
                    print killstdout
                if killsterr:
                    print killsterr
                # os.kill(pid, signal.SIGKILL)
                # os.kill(pid, signal.9) #　与上等效
                print 'Killed server:%s, pid:%s' % (serverName, pid_TMP)
        except OSError, e:
            print 'No such as server!', e
        if getPid(serverName):
            print "shutdown fail,check server:%s" % serverName
            return False
    else:
        print "Server:%s,shutdown success" % serverName
        return True

def unzipWar(zipfilePath,unzipfilepath):
    f = zipfile.ZipFile(zipfilePath, 'r')
    print 'unzip file:%s >>>>>>to:%s' % (zipfilePath, unzipfilepath)
    for file in f.namelist():
        f.extract(file, unzipfilepath)

def reNameCatalina(serverName):
    deployServerLogsDir = getDeploymentTomcatPath(serverName)["deployServerLogsDir"]
    deployServerLogsDirBak = getDeploymentTomcatPath(serverName)["deployServerLogsDirBak"]
    if os.path.exists(deployServerLogsDir):
        if not os.path.exists(deployServerLogsDirBak):
            myloger(serverName, msg="重命名%s 》》 %s" % (deployServerLogsDir, deployServerLogsDirBak))
            os.rename(deployServerLogsDir,deployServerLogsDirBak)

def startServer(serverName):
    now = datetime.datetime.now()
    data_time = now.strftime('%Y-%m-%d')
    serverNameDict = serverNameDictList[serverName]
    deploydir = serverNameDict["deployDir"]
    jar = serverNameDict["war"]
    jarName = jar.split("/")[-1]
    deployjar = os.path.join(deploydir, jarName)
    deployDir = getDeploymentTomcatPath(serverName)["deployServerTomcatDir"]
    serverlogpath = os.path.join(logsPath, "%s-%s.log") % (serverName, data_time)
    xms = serverNameDict["xms"]
    xmx = serverNameDict["xmx"]
    jmxport = serverNameDict['jmx_port']
    # ip = confDict[]
    startSh = os.path.join(deployDir, "bin/startup.sh")
    print typeName
    if typeName == "jar":
        rootJar = os.path.join(deploydir,"ROOT.jar")
        # if os.path.exists(deployjar) and os.path.exists(rootJar):
        if os.path.exists(rootJar):
            # print "删除文件%s" % deployjar
            myloger(serverName,msg= "删除文件%s" % deployjar)
            if os.path.exists(deployjar):
                os.remove(deployjar)
                # print "重命名%s 》》 %s" %(rootJar,deployjar)
                myloger(serverName, msg="重命名%s 》》 %s" %(rootJar,deployjar))
            os.rename(rootJar,deployjar)
        if envName == "dev":
            deploynode = serverNameDict["devNodeName"][0]
        if envName == "test":
            deploynode = serverNameDict["testNodeName"][0]
        if envName == "pro":
            deploynode = serverNameDict["proNodeName"][0]
        ip = hostDict[deploynode]
        cmd = """sudo su - tomcat -c '%s %s -Xms%s -Xmx%s \
                -Dcom.sun.management.jmxremote.port=%s \
                -Dcom.sun.management.jmxremote.authenticate=false \
                -Djava.rmi.server.hostname=%s \
                -Dcom.sun.management.jmxremote.ssl=false -jar %s >%s 2>&1 &'""" % (nohup,java,xms, xmx,jmxport ,ip,deployjar,serverlogpath)
    else:
        cmd = "sudo su - tomcat -c '/bin/bash %s'" % startSh
    binDir = os.path.join(deployDir, "bin/*")
    deployServerWarDir = getDeploymentTomcatPath(serverName)["deployServerWarDir"]

    pid = getPid(serverName)
    if not pid:
        # 每次启动重新命名catalina 防止一直增长
        #使用lograted 配置
        #reNameCatalina(serverName)
        myloger(serverName, msg="Start Server:%s" % serverName)
        stdout, stderr = execSh(cmd)  # 执行 启动服务命令
        if stdout:
            print "stdout:%s" % stdout
        if stderr:
            print "stderr:%s " % stderr
        for i in range(checktime):
                # time.sleep(5)
            print "check servname :%s num:%s" % (serverName, i + 1)
            # myloger(serverName, msg="check servname :%s num:%s" % (serverName, i + 1))
            pidtmp = getPid(serverName)
            if typeName == "jar":
                print "Server:%s,start success pid:%s" % (serverName, pidtmp)
                # myloger(serverName, msg="Server:%s,start success pid:%s" % (serverName, pidtmp))
                return True
            else:
                res = checkStartSucss(serverName)
                if pidtmp and res:
                    print "Server:%s,start success pid:%s" % (serverName, pidtmp)
                    # myloger(serverName, msg="Server:%s,start success pid:%s" % (serverName, pidtmp))
                    return True
        pidtmp = getPid(serverName)
        if typeName == "jar":
            res = True
        else:
            res = checkStartSucss(serverName)
        if getPid(serverName) and res:
            print "Server:%s,Sucess pid:%s" % (serverName, pidtmp)
            # myloger(serverName, msg="Server:%s,start success pid:%s" % (serverName, pidtmp))
            return True
        else:
            print "Server:%s,is not running" % serverName
            # myloger(serverName, msg="Server:%s,is not running" % serverName)
            return False
    else:
        pidtmp = getPid(serverName)
        print "Server:%s,Sucessed pid:%s" % (serverName, pid)
        # myloger(serverName, msg="Server:%s,start success pid:%s" % (serverName, pidtmp))
        return True

def cleanDeployDir(serverName):

    deploymentAppPath = getDeploymentTomcatPath(serverName)["deployServerDir"]
    try:
        shutil.rmtree(deploymentAppPath)
        print "clean %s" % deploymentAppPath
    except Exception, e:
        print e
        sys.exit()

def copyBaseTomcat(serverName):

    deploymentDirTmp = getDeploymentTomcatPath(serverName)["deployServerDir"]
    try:
        print "copy BaseTomcat Dir :%s to:%s" % (baseTomcat, deploymentDirTmp)
        shutil.copytree(baseTomcat, deploymentDirTmp)
    except Exception, e:
        print e, "dir is exists！"
        sys.exit(1)

# 修改xml 配置文件
def changeXml(serverName,shutdown_port="8128",http_port="8083",ajp_port="8091"):
    deployPath = getDeploymentTomcatPath(serverName)
    warDir = deployPath["deployServerWarDir"]  # 解压的war 目录
    xmlpath = deployPath["deployServerXmlDir"]
    print xmlpath
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
        Executor[0].setAttribute("name", serverName+"-tomcatThreadPool")
        appdeploy = i.getElementsByTagName("Host")
        appdeploy[0].setAttribute("appBase", "webapps") #部署目录 默认为webapps
        connector[0].setAttribute("port", str(http_port))  # http port
        connector[0].setAttribute("executor", serverName+"-tomcatThreadPool")  # http port
        # connector[1].setAttribute("port", str(ajp_port))  # ajp port
    outfile = file(xmlpath, 'w')
    write = codecs.lookup("utf-8")[3](outfile)
    domtree.writexml(write, addindent=" ", encoding='utf-8')
    write.close()

def myloger(name="debugG",logDir="/tmp",level="INFO",msg="default test messages"):
    logPath = os.path.join(logDir, "logger")
    if not os.path.exists(logPath):
        os.makedirs(logPath)
    logPath = os.path.join(logPath, "{name}.log").format(name=name)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s:%(message)s')
    logger = logging.getLogger(name)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    fileLog = logging.handlers.TimedRotatingFileHandler(filename=logPath, when="D", interval=1, backupCount=5)
    fileLog.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(console)
    logger.addHandler(fileLog)
    "CRITICAL：50，ERROR：40，WARNING：30，INFO：20，DEBUG：10，NOTSET：0。"
    # linetmp = "#"*20
    # infoTmp = "{lintmp}{level}{lintmp}".format(lintmp=linetmp,level=level)
    if level == "INFO":
        # print "%s：test==%s" % (level,msg)
        logger.info(msg)
    elif level == "ERROR":
        logger.error(msg)
    elif level == "WARNING":
        # print "%s：test" % level
        logger.warning(msg)
    elif level == "CRITICAL":
        # print "%s：test" % level
        logger.critical(msg)
    else:
        # print "%s：test" % level
        logger.debug(msg)
    logger.removeHandler(console)
    logger.removeHandler(fileLog)

def execSh1(cmd,print_msg=True):
    # 执行SH命令
    stdout_lines = ""
    stderr_lines = ""
    linetmp = "#" * 30
    infoTmp = "{lintmp}{level}{lintmp}".format(name=serverName,lintmp=linetmp, level="INFO")
    errorTmp = "{lintmp}{level}{lintmp}".format(name=serverName,lintmp=linetmp, level="ERROR")
    try:
        print "执行ssh 命令： %s" % cmd
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        if p.stdout:
            myloger(name=serverName, msg=infoTmp, level="INFO")
            for line in iter(p.stdout.readline, ''):
                if print_msg:
                    # checkError(serverName,line.rstrip())
                    myloger(name=serverName, msg=line.rstrip())
                stdout_lines += line
        if p.stderr:
            myloger(name=serverName, msg=errorTmp, level='ERROR')
            for err in iter(p.stderr.readline, ''):
                if print_msg:
                    # checkError(serverName, err.rstrip())
                    myloger(name=serverName, level="ERROR", msg=err.rstrip())
                stderr_lines += err

        p.wait()
        print "执行命令结束"
    except Exception, e:
        print e,
        sys.exit()
    return stdout_lines, stderr_lines

def execSh(cmd):
    # 执行SH命令
    try:
        print "执行ssh命令 %s" % cmd
        # myloger(serverName,msg="执行ssh b命令 %s" % cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    except Exception, e:
        print e,
        sys.exit()
    return p.communicate()


def versionSort(list):
  #对版本号排序 控制版本的数量
    from distutils.version import LooseVersion
    vs = [LooseVersion(i) for i in list]
    vs.sort()
    return [i.vstring for i in vs]

def getVersion(serverName):

    bakdeployRoot = getDeploymentTomcatPath(serverName)["bakServerDir"]

    # getDeploymentTomcatPath(serverName)["bakServerDir"]
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
    return versionSort(versionIdList)  # 返回版本号升序列表

def getBackVersionId(serverName):
    date = time.strftime("%Y-%m-%d")
    versionIdList = getVersion(serverName)
    # print versionIdList
    if not versionIdList:
        return 1
    else:
        # 同一日期下的最新版本+1
        if date != versionSort(versionIdList)[-1].split("-V")[0]:
            return 1
        else:
            return int(versionIdList[-1].split("-")[-1].split("V")[-1]) + int(1)

def TimeStampToTime(timestamp):
    # 时间戳转换为时间
    timeStruct = time.localtime(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S', timeStruct)

# 返回时间戳
def getTimeStamp(filePath):
    filePath = unicode(filePath, 'utf8')
    t = os.path.getmtime(filePath)
    # return t
    return TimeStampToTime(t)

#清理历史多余的备份文件和原来的war包
def cleanHistoryBak(serverName):
    bakServerDir = getDeploymentTomcatPath(serverName)["bakServerDir"]

    VersinIdList = getVersion(serverName)
    # print VersinIdList
    if VersinIdList:
        if len(VersinIdList) > int(bakNum):
            cleanVersionList = VersinIdList[0:abs(len(VersinIdList) - int(bakNum))]
            for i in cleanVersionList:
                bakWarPath = os.path.join(bakServerDir, "war.%s") % i
                if os.path.exists(bakWarPath):
                    print "clean history back WAR: %s" % bakWarPath
                    os.remove(bakWarPath)
                    # shutil.rmtree(bakWarPath)
        else:
            pass
    else:
        print "%s is not bak War" % serverName


def copyFile(sourfile,disfile):
    try:
        print "copy file:%s,to:%s" % (sourfile, disfile)
        shutil.copy2(sourfile, disfile)  # % ( disfile, time.strftime("%Y-%m-%d-%H%M%S"))
    except Exception, e:
        print e,
        sys.exit(1)

def copyDir(sourDir,disDir):
    try:
        print "copy Dir:%s,to:%s" % (sourDir,disDir)
        # shutil.copy2(sourDir, disDir)  # % ( disfile, time.strftime("%Y-%m-%d-%H%M%S"))
        shutil.copytree(sourDir,disDir)
    except Exception, e:
        print e,
        sys.exit(1)

def cleanROOT(serverName):

    deployServerWarDir = getDeploymentTomcatPath(serverName)["deployServerWarDir"]
    if os.path.exists(deployServerWarDir):
        print "clean history ROOT dir: %s" % deployServerWarDir
        # os.remove(bakWarPath)
        shutil.rmtree(deployServerWarDir)
        return True

def cleanRootTomcat(serverName,action):

    deployServerWarDir = getDeploymentTomcatPath(serverName)["deployServerWarDir"]
    deployWar = getDeploymentTomcatPath(serverName)["deployServerWar"]
    if action == "delwar":
        if os.path.exists(deployWar):
            print "clean history war : %s" % deployWar
            os.remove(deployWar)
            # shutil.rmtree(deployWar)
            return True
    elif action == "delroot":
        if os.path.exists(deployServerWarDir):
            print "clean history ROOT dir: %s" % deployServerWarDir
            # os.remove(bakWarPath)
            shutil.rmtree(deployServerWarDir)
            return True
    else:
        pass


def backWar(serverName):

    if typeName == "jar":
        serverNameDict = serverNameDictList[serverName]
        deploydir = serverNameDict["deployDir"]
        jar = serverNameDict["war"]
        jarName = jar.split("/")[-1]
        deployWar = os.path.join(deploydir, jarName)
    else:
        # 部署的war包
        deployWar = getDeploymentTomcatPath(serverName)["deployServerWar"]
    # 备份war包路径
    bakServerDir = getDeploymentTomcatPath(serverName)["bakServerDir"]
    if not os.path.exists(bakServerDir):
        os.mkdir(bakServerDir)
    print bakServerDir
    versionId = getBackVersionId(serverName)  # 同一日期下的最新版本
    print versionId
    try:
        lastVersinId = getVersion(serverName)[-1]
    except:
        # 获取 备份文件列表 如果没有备份 返回备份起始版本1
        lastVersinId = [time.strftime("%Y-%m-%d-")+"V1"][-1]
        # print lastVersinId
    if typeName == "jar":
        bakdeployRootWar = os.path.join(bakServerDir, "jar.%sV%s") % (time.strftime("%Y-%m-%d-"), versionId)
        lastbakdeployRootWar = os.path.join(bakServerDir, "jar.%s") % (lastVersinId)
    else:
       bakdeployRootWar = os.path.join(bakServerDir,"war.%sV%s") % (time.strftime("%Y-%m-%d-"), versionId)
       lastbakdeployRootWar = os.path.join(bakServerDir,"war.%s") % (lastVersinId)

    if not checkServer(serverName):
        print "%s is not install" % serverName
    else:
        if os.path.exists(deployWar):
            if not os.path.exists(lastbakdeployRootWar):
                print "back %s >>> %s" % (deployWar, bakdeployRootWar)
                copyFile(deployWar, bakdeployRootWar)
                # copyDir(deployWar, bakdeployRootWar)
            else:
                # 判断 最后一次备份和现在的文件是否 修改不一致，如果一致就不备份，
                if not getTimeStamp(deployWar) == getTimeStamp(lastbakdeployRootWar):
                    print "back %s >>> %s" % (deployWar, bakdeployRootWar)
                    # copyDir(deployWar, bakdeployRootWar)
                    copyFile(deployWar,bakdeployRootWar)
                    cleanHistoryBak(serverName)
                    if os.path.exists(bakdeployRootWar):
                        print "back %s sucess" % bakdeployRootWar
                    else:
                        print "back %s fail" % deployWar
                else:
                    # print getVersion(serverName)
                    print "File:%s is not modify,not need back" % deployWar
        else:
            print "file %s or %s is not exists" % (deployWar, bakdeployRootWar)

def rollBack(serverName,version=""):
    dirDict = getDeploymentTomcatPath(serverName)
    versionList = getVersion(serverName)
    if typeName == "jar":
        serverNameDict = serverNameDictList[serverName]
        deploydir = serverNameDict["deployDir"]
        jar = serverNameDict["war"]
        jarName = jar.split("/")[-1]
        deployWar = os.path.join(deploydir, jarName)

    if not versionList:
        print "Not Back war File :%s" % serverName
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
        if not os.path.exists(deployRootWar):
            print "File:%s is not exits" % deployRootWar
        if os.path.exists(deployServerWar):
            # shutil.rmtree(deployServerWar)
            # shutil.remove(deployServerWar)
            os.remove(deployServerWar)
            print "clean history file: %s " % deployServerWar
        if os.path.exists(deployRootWar):
            # os.removedirs(deployRootWar)
            shutil.rmtree(deployRootWar)
            print "clean history file: %s " % deployRootWar
        # copyDir(bakdeployWar, deployRootWar)
        copyFile(bakdeployWar, deployServerWar)
        chownCmd = "chown -R tomcat:tomcat %s" % deployServerWar  # 目录权限修改
        stdout, stderr = execSh(chownCmd)
        if stdout:
            print stdout
        if stderr:
            print stderr
        # print"%s install sucess" % serverName
        if os.path.exists(deployServerWar):
            print "RollBack Sucess,update serverName:%s" % serverName
            print "Rollback Version:%s " % versionId
        else:
            print "check File:%s ,rollback Faile" % deployServerWar

def ReturnExec(cmd):
    stdout, stderr = execSh(cmd)
    if stdout:
        print 80*"#"
        print "out:%s " % stdout
    if stderr:
        print 80*"#"
        print "err:%s" % stderr

def checkStartSucss(serverName):
    serverDict = getDeploymentTomcatPath(serverName)
    # deployServerWarDir = serverDict["deployServerWarDir"]
    deployServerLogsDir = serverDict["deployServerLogsDir"]
    cmd = "tail -F %s" % deployServerLogsDir
    print(cmd)
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    num = 1
    while True:
        for line in iter(p.stdout.readline, ''):
            num += 1
            # print " stdout:%s " % line.rstrip()
            print (line.rstrip())
            if "Server startup in" in line:
                print "check server started Success"
                return True
            if num >= 200:
                print "check server started False"
                return False
        print "check server started status line num: %s" % num
        p.wait()

"ln -s /home/tomcat/upload/resouces /project/project-deploy/xkj-upload/webapps/ROOT/resouces"

def uploadResourInit(serverName):
    serverDict = getDeploymentTomcatPath(serverName)
    deployServerWarDir = serverDict["deployServerWarDir"]
    resoucesDir = os.path.join(deployServerWarDir,"resouces")
    try:
        shutil.rmtree(resoucesDir)
        print "clean %s" % resoucesDir
    except Exception, e:
        print e
        sys.exit()
    lnsCmd = "ln -s {sourDir} {linkDir}".format(sourDir=uploadsourDir,linkDir=resoucesDir)
    if not os.path.exists(uploadsourDir):
        print "%s is not exists init mkdir " % uploadsourDir
        os.makedirs(uploadsourDir)
        chownCmd = "chown -R tomcat:tomcat %s" % uploadsourDir  # 目录权限修改
        nignxAddNginxCmd = "usermod -a -G tomcat nginx"   # 加入tomcat 用户组而不离开原来的用户组
        stdout, stderr = execSh(nignxAddNginxCmd)
        stdout, stderr = execSh(chownCmd)
        if stdout:
            print"stdout:", stdout
        if stderr:
            print "stderr:", stderr
        if os.path.exists(uploadsourDir):
            print "%s init sucesss" % uploadsourDir
        else:
            print " init mkdir false please check " % uploadsourDir
            sys.exit(1)
    stdout,stderr = execSh(lnsCmd)
    if stdout:
        print"stdout:", stdout
    if stderr:
        print "stderr:", stderr

def sendWarToNode(serverName,envName):
    serverDict = getDeploymentTomcatPath(serverName)
    deployServerWarDir = serverDict["deployServerWarDir"]
    war = serverDict["war"]
    if envName == "test":
        deployNode = serverNameDict[serverName]["testNodeName"]
    elif envName == "dev":
        deployNode = serverNameDict[serverName]["devNodeName"]
    elif envName == "pro":
        deployNode = serverNameDict[serverName]["proNodeName"]
    else:
        print("not env name")
        sys.exit()
    CopyZipFile = "ansible  %s -f 5 -i %s -m unarchive -a 'src=%s dest=%s copy=yes owner=tomcat group=tomcat backup=yes'" % (
        deployNode, ansibleHost, war, deployServerWarDir)
    ReturnExec(CopyZipFile)

def main(action,serverName,version,envName):
    action = action.lower()
    if action =="install":
        installServer(serverName)
        changeCatalina(serverName)
    elif action == "uninstall":
        uninstallServer(serverName)
    elif action == "stop":
        stopServer(serverName)
    elif action == "start":
        startServer(serverName)
    elif action == "restart":
        stopServer(serverName)
        startServer(serverName)
    elif action == "reinstall":
        uninstallServer(serverName)
        installServer(serverName)
        changeCatalina(serverName)
    elif action == "back":
        backWar(serverName)
    elif action == "cleanroot":
        cleanROOT(serverName)
    elif action == "delroot":
        cleanRootTomcat(serverName,action)
    elif action == "delwar":
        cleanRootTomcat(serverName, action)
    elif action == "changmen":
        changeCatalina(serverName)
    elif action == "changxml":
        changeXML(serverName)
        # cleanROOT(serverName)
    elif action == "status":
        if not getPid(serverName):
            print "%s is stoped" % serverName
        else:
            print "%s is started" % serverName
        # print {serverName: "started"}
        # return {serverName: "started"}
    elif action == "uploadresour":
        uploadResourInit(serverName)
    elif action == "rollback":
        stopServer(serverName)
        rollBack(serverName, version)
        startServer(serverName)
    elif action == "getback":
        versionlist = getVersion(serverName)
        if not versionlist:
            print "%s not back" % serverName
        else:
            print "%s has back version:%s" % (serverName, versionlist)
    else:
        print "action is -a 111 [deploy,install,uninstall,reinstall,stop,start,restart,back,rollback,getback] -n servername [all]"
        print "action:(%s)" % action
        print "env:%s" % envName
        sys.exit(1)

if __name__ == "__main__":

    # getip()
    # sys.exit()
    # serverConf_test = "startServer.yml"  # 部署配置文件
    # serverconf = "/tmp/pycharm_project_651/python_project/serverConf.yml"
    serverconf = "/python_yek/serverConf.yml"
    # serverconf = "/data/init/serverConf.yml"
    confDict = readYml(serverconf)
    mvn = confDict["mvn"]
    hostDict = confDict["hostDict"]
    # remote_py = confDict["remotePy"]
    tomcatPrefix = confDict["tomcatPrefix"]
    baseTomcat = confDict["baseTomcat"]
    deploymentAppDir = confDict["deploymentAppDir"]
    python = confDict["python"]
    checktime = confDict["checkTime"]
    java = confDict["java"]
    nohup = confDict["nohup"]
    startConf = confDict["startServer"]
    ansibleHost = confDict["ansibileHost"]
    bakDir = confDict["bakDir"]
    logsPath = confDict["logsPath"]
    bakNum = confDict["bakNum"]
    # warConf = confDict["warConf"]
    uploadsourDir = confDict["uploadsourDir"]

    options, args = getOptions()
    action = options.action
    version = options.versionId
    serverName = options.serverName
    envName = options.envName
    typeName = options.typeName
    warConf = confDict["warConf"].format(env=envName)

    _init(warConf)

    if serverName == "all":
        for serverNameDict in serverNameDictList:
            for seName, portDict in serverNameDict.iteritems():
                main(action, seName, version, envName)
                # if checkStartSucss(seName):
                #     pass
    else:
       main(action, serverName, version, envName)

