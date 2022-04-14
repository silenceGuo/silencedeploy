#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 2019-8-19 下午 14:38 
# @Author : damon.guo 
# @File : deploy-tomcat-control-V2.py 
# @Software: PyCharm
import os
import sys
import time
from optparse import OptionParser
from subprocess import PIPE,Popen
import json
import yaml
import Queue
import threading
import logging
import shutil
from logging import handlers
import copy
# yaml.warnings({'YAMLLoadWarning': False})
"""
1, 代码繁杂，存在冗余，功能结构不清晰
2，环境配置文件，内存设置。可以在归总到一个，部署节点修改非列表方式
3，tomcat 启动参数修改，可优化，目前是至读取第2行内容，已经修改模板化
4，清除垃圾代码
5，不够pythonic
"""
def myloger(name="debugG", logDir="/tmp", level="INFO",msg="default test messages"):
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
    if level == "INFO":
        logger.info(msg)
    elif level == "ERROR":
        logger.error(msg)
    elif level == "WARNING":
        logger.warning(msg)
    elif level == "CRITICAL":
        logger.critical(msg)
    else:
        logger.debug(msg)
    logger.removeHandler(console)
    logger.removeHandler(fileLog)

def execSh(cmd,print_msg=True):
    # 执行SH命令
    stdout_lines = ""
    stderr_lines = ""
    try:
        # print "执行ssh 命令： %s" % cmd
        myloger(name=serverName, level="INFO", msg="执行命令:%s" % cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        if p.stdout:
            for line in iter(p.stdout.readline, ''):
                if print_msg:
                    myloger(name=serverName, msg=line.rstrip())
                else:
                    print(line.rstrip())
                stdout_lines += line
        if p.stderr:
            for err in iter(p.stderr.readline, ''):
                if print_msg:
                    myloger(name=serverName, level="ERROR", msg=err.rstrip())
                else:
                    print(line.rstrip())
                stderr_lines += err
        p.wait()
        myloger(name=serverName, level="INFO", msg="执行命令结束")
    except Exception, e:
        print e
        sys.exit()
    return stdout_lines, stderr_lines

def readConfAnsible(file):
    import configparser
    if not os.path.exists(file):
        sys.exit()
    cf = configparser.ConfigParser(allow_no_value=True)
    cf.read(file)
    try:
        cf.read(file)
    except ConfigParser.ParsingError, e:
        print e
        print "请检查ansible服务主机文件 %s" % file
        sys.exit()
    groupNameDict = {}
    for groupName in cf.sections():
        iplist = []
        for ipstr in cf.options(groupName):
            ip = ipstr.split(" ")[0]
            iplist.append(ip)
            # print groupName, ip
        groupNameDict[groupName] = iplist
    return groupNameDict

def sshAddHost():
    # 配置添加免密主机
    stdout, stderr = execSh('ansible --version')
    if stderr:
        stdout, stderr = execSh("yum install ansible -y")
    playbookYml = confDict["playbookYml"]
    sshDict = readYml(playbookYml)
    hosts = sshDict[0]["hosts"]
    hostsDict = readConfAnsible(ansibleHost)
    y = raw_input("是否需要重新生成私钥和公钥：y/n")
    if y.lower() == 'y':
        execSh("ssh-keygen -t rsa -b 2048 -P '' -f /root/.ssh/id_rsa")
    execSh("export ANSIBLE_HOST_KEY_CHECKING=False")
    if hosts not in hostsDict:
        myloger(name="init", msg="{playbookYml}的hosts分组在{ansibleHost}中不存在，请配置好{ansibleHost}中分组{hosts}"
                .format(playbookYml=playbookYml, ansibleHost=ansibleHost, hosts=hosts))
        myloger(name="init", msg="""如下示例:
                                   [{hosts}]
                                   192.168.254.84 ansible_ssh_pass=123456 ansible_ssh_user=root ansible_ssh_port=22""".format(
            hosts=hosts))
    else:

        for ip in hostsDict[hosts]:
            execSh("ssh-keyscan {ip} >> /root/.ssh/known_hosts".format(ip=ip))
        execSh("ansible-playbook -i {hosts} {playbookYml}".format(hosts=ansibleHost, playbookYml=playbookYml))

def checkError(serName,strinfo):
    if "error" in strinfo.lower():
        # myloger(name=serName, level="ERROR", msg=strinfo)
        myloger(name=serName, level="ERROR", msg=strinfo)
        return False
    elif "fatal" in strinfo.lower():
        myloger(name=serName, level="ERROR", msg=strinfo)
        return False
    elif "false" in strinfo.lower():
        myloger(name=serName, level="ERROR", msg=strinfo)
        return False
    else:
        myloger(name=serName, level="INFO", msg=strinfo)
        return True

def execAnsible(serverName,deploynode,action,env,typeName,version="-1"):
    serverNameDict = projectDict[serverName]
    statusDict = {}
    myloger(name=serverName, level="INFO", msg=" server:%s is %s now " % (serverName,action))
    cmd = "ansible %s -i %s -m shell -a '%s %s -a %s -n %s -e %s -t %s -v %s'" % (
        deploynode, ansibleHost, python, remote_py, action, serverName, env,typeName,version)
    if action == "start":
        stdout, stderr = execSh(cmd)
    else:
        stdout, stderr = execSh(cmd)
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

def execAnsibleNg(serverName,deploynode,urlName,action,ipPort,configPath,templatePath):
    myloger(name=serverName, level="INFO", msg=" server:%s is %s now " % (serverName,action))
    cmd = "ansible {deploynode} -i {ansibleHost} -m shell -a " \
          "'{python} {makeNginxConf} -a {action} -i {ipPort} -n {urlName} -t {templatePath} -c {configPath}'".format(
        deploynode=deploynode,
        ansibleHost=ansibleHost,
        python=python,
        urlName=urlName,
        makeNginxConf=makeNginxConf,
        action=action,
        serverName=serverName,
        ipPort=ipPort,
        configPath=configPath,
        templatePath=templatePath)
    stdout, stderr = execSh(cmd)
    if "test failed" in stdout:
        myloger(serverName, level="ERROR", msg="%s %s False on %s " % (serverName, action, deploynode))
        return False
    elif "test failed" in stderr:
        myloger(serverName, level="ERROR", msg="%s %s False on %s " % (serverName, action, deploynode))
        return False
    else:
        myloger(serverName, level="INFO", msg="%s %s True on %s " % (serverName, action, deploynode))
        return True

def execAnsibleDir(serverName,action,env):
    serverNameDict = projectDict[serverName]
    deployDir = serverNameDict["deployDir"]
    myloger(name=serverName, level="INFO", msg=" server:%s is %s now " % (serverName,action))
    deploynode = serverNameDict["{envName}NodeName".format(envName=envName)][0]
    if action == "install":
        cmd = "ansible %s -i %s -m file -a 'path=%s state=directory owner=tomcat group=tomcat'" % (
            deploynode, ansibleHost, deployDir)
    elif action == "uninstall":
        cmd = "ansible %s -i %s -m file -a 'path=%s state=absent owner=tomcat group=tomcat'" % (
            deploynode, ansibleHost, deployDir)

    stdout, stderr = execSh(cmd)
    if "FAILED" in stdout:
        myloger(serverName, level="ERROR", msg="%s %s False on %s " % (serverName, action, env))
        return False
    elif "FAILED" in stderr:
        myloger(serverName, level="ERROR", msg="%s %s False on %s " % (serverName, action, env))
        return False
    else:
        myloger(serverName, level="INFO", msg="%s %s True on %s " % (serverName, action, env))
        return True

def getDeploymentTomcatPath(serverName):
    deployServerDir = os.path.join(deploymentAppDir, "%s%s") % (tomcatPrefix, serverName)
    deployServerWarDir = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName, "webapps/ROOT")
    deployServerWar = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName, "webapps/ROOT.war")
    deployServerTomcatDir = os.path.join(deploymentAppDir, "%s%s") % (tomcatPrefix, serverName)
    deployServerXmlDir = os.path.join(deploymentAppDir, "%s%s/%s") % (tomcatPrefix, serverName,"conf/server.xml")
    bakServerDir = os.path.join(bakDir, "%s%s") % (tomcatPrefix, serverName)
    return {"deployServerDir":deployServerDir,
            "deployServerWarDir":deployServerWarDir,
            "deployServerTomcatDir":deployServerTomcatDir,
            "deployServerXmlDir":deployServerXmlDir,
            "bakServerDir": bakServerDir,
            "deployServerWar": deployServerWar
            }

def deploy_node(serverName,deploynode,typeName):
    # print "发送文件至远程节点 "
    myloger(serverName, level="INFO", msg="发送文件至远程节点 ")
    serverDict = getDeploymentTomcatPath(serverName)
    serverNameDict = projectDict[serverName]
    if typeName == "jar":
        # 为在发布前提前打包 发送到目标服务器，jar名称不能一样
        deployServerWar = os.path.join(serverNameDict["deployDir"],"ROOT.jar")
    else:
        deployServerWar = serverDict["deployServerWar"]
    war = projectDict[serverName]["war"]
    copyFILE = 'ansible %s -i %s -m copy -a "src=%s dest=%s owner=tomcat group=tomcat"' % (deploynode, ansibleHost, war, deployServerWar)
    execSh(copyFILE)

def syncJarconf(deploynode,deployFile,deployDir):
    copyFILE = 'ansible %s -f 5 -i %s -m copy -a "src=%s dest=%s owner=tomcat group=tomcat"' % (deploynode, ansibleHost, deployFile, deployDir)
    stdout, stderr = execSh(copyFILE, print_msg=True)
    if checkError(serverName, stdout) and checkError(serverName, stderr):
        return True
    return False

def execAnsibleTomcat(serverName,action,env):
    serverNameDict = projectDict[serverName]
    print " server:%s is %s now " % (serverName,action)

    deploydir = serverNameDict["deploydir"]
    # if env == "dev":
    #     deploynode = serverNameDict["devnodename"]
    # if env == "test":
    #     deploynode = serverNameDict["testnodename"]
    # if env == "pro":
    #     deploynode = serverNameDict["pronodename"]
    deploynode = serverNameDict["{envName}NodeName".format(envName=envName)][0]
    cmd = "ansible %s -i %s -m shell -a '%s %s -a %s -n %s -e %s'" % (
        deploynode, ansibleHost, python, remote_py, action, serverName, env)
    stdout,stderr = execSh(cmd)
    if checkError(serverName, stdout) and checkError(serverName, stderr):
        return True
    return False

def checkMaster(branchName):
    # 获取项目分支是否为master
    cmd = "git branch"
    stdout, stderr = execSh(cmd)
    print "out:", stdout
    branch_list = [i.strip() for i in stdout.split("\n") if i]
    branchName_str = "* %s" % branchName
    if branchName_str in branch_list:
        print "%s 分支" % branchName
        return True
    print "err", stderr
    return False

def gitupdate(serverName,branchName):
    serverNameDict = projectDict[serverName]
    # deployDir = serverNameDict["deploydir"]
    buildDir = serverNameDict["buildDir"]
    os.chdir(buildDir)
    if not checkMaster(branchName):
        checkout_m_cmd = "git checkout %s" % branchName
        print "切换至%s分支" % branchName
        execSh(checkout_m_cmd)

    print "获取 最新%s分支" % branchName
    pull_m_cmd = "git pull"
    stdout, stderr = execSh(pull_m_cmd)
    # 判断是否有git 执行错误
    return checkError(stdout, stderr)

# jar 文件mavn构建
def buildMaven(serverName,branchName,typeName):

    serverNameDict = projectDict[serverName]
    buildDir = serverNameDict["buildDir"]
    if typeName == "svn":
        svnUpdate(serverName)
    elif typeName == "jar":
        svnUpdate(serverName)
        return buildJar(serverName,branchName,typeName)
    else:
        if not gitupdate(serverName,branchName):
            print "git update is err"
            sys.exit(1)
        os.chdir(buildDir)
    # 代码扫描
    # sonar(serverName)
    # print "workdir : %s" % os.getcwd()
    myloger(name=serverName, level="INFO", msg="workdir : %s" % os.getcwd())
    # cmd = "%(mvn)s clean && %(mvn)s install -Dmaven.test.skip=true -P dev" % {"mvn": mvn}
    cmd = "%(mvn)s clean && %(mvn)s install" % {"mvn": mvn}

    msg = "构建服务：%s" % serverName
    myloger(serverName, msg=msg)
    # sys.exit()
    stdout, stderr = execSh(cmd)

    if "BUILD FAILURE" in stdout:
        return False
    elif "BUILD FAILURE" in stderr:
        return False
    else:
        # 重新添加配置文件 重新构建war包
        addconfToWar(serverName, envName,typeName)
        return True

def addResource(serverName,envName,typeName):
    serverNameDict = projectDict[serverName]
    serverDict = getDeploymentTomcatPath(serverName)
    if typeName == "svn":
        serverNameEnvConfDir = os.path.join(svnConfigDir, serverName, "sys-%s") % envName
    elif typeName == "jar":
        serverNameEnvConfDir = os.path.join(configDir, serverName, "resources-%s") % envName
    else:
        os.chdir(configDir)
        print "获取新配置"
        pull_m_cmd = "git pull"
        stdout, stderr = execSh(pull_m_cmd)
        # 判断是否有git 执行错误
        isNoErr(stdout, stderr)
        serverNameEnvConfDir = os.path.join(configDir, serverName, "sys-%s") % envName
    serverNameTargetDir = serverNameDict["targetDir"]
    serverNamebuildDir = serverNameDict["buildDir"]

    if os.path.exists(serverNameTargetDir):
        print "清理默认的sys目录"
        shutil.rmtree(serverNameTargetDir)
    try:
        print
        "copy sysconfig Dir :%s to:%s" % (serverNameEnvConfDir, serverNameTargetDir)
        shutil.copytree(serverNameEnvConfDir, serverNameTargetDir)
    except Exception, e:
        print e, "dir is exists！"
        sys.exit(1)

def buildJar(serverName,branchName,typeName):

    serverNameDict = projectDict[serverName]
    buildDir = serverNameDict["buildDir"]

    addResource(serverName,envName,typeName)
    os.chdir(buildDir)
    # print "workdir : %s" % os.getcwd()
    myloger(name=serverName, level="INFO", msg="workdir : %s" % os.getcwd())
    # cmd = "%(mvn)s clean && %(mvn)s install -Dmaven.test.skip=true -P dev" % {"mvn": mvn}
    cmd = "%(mvn)s clean && %(mvn)s install" % {"mvn": mvn}

    msg = "构建服务：%s" % serverName
    myloger(serverName, msg=msg)
    # sys.exit()
    stdout, stderr = execSh(cmd)

    if "BUILD FAILURE" in stdout:
        return False
    elif "BUILD FAILURE" in stderr:
        return False
    else:
        return True

# 解析 ansible 输出
def parseAnsibleOut(stdout):
    try:
        splitList = stdout.split("SUCCESS => ")
        d = splitList[1].strip()
        t = json.loads(d)
        exists = t["stat"]["exists"]
        return exists
    except:
        pass

def ansibileSyncDir(ip,sourceDir,destDir):
    SyncDir = "ansible %s -m synchronize -a 'src=%s dest=%s'" % (ip, sourceDir, destDir)

    """
    ansible test -m synchronize -a 'src=/etc/yum.repos.d/epel.repo dest=/tmp/epel.repo' -k                  # rsync 传输文件
    ansible test -m synchronize -a 'src=/tmp/123/ dest=/tmp/456/ delete=yes' -k                             # 类似于 rsync --delete
    ansible test -m synchronize -a 'src=/tmp/123/ dest=/tmp/test/ rsync_opts="-avz,--exclude=passwd"' -k    # 同步文件，添加rsync的参数-avz，并且排除passwd文件
    ansible test -m synchronize -a 'src=/tmp/test/abc.txt dest=/tmp/123/ mode=pull' -k                      # 把远程的文件，拉到本地的/tmp/123/目录下　　
    """
    execSh(SyncDir)

def ansibileCopyZipFile(serverName):
    nodeName = projectDict[serverName]["deploygroupname"]
    deployDir = projectDict[serverName]["deploydir"]

    deployFile = projectDict[serverName]["jar"]
    CopyZipFile = "ansible %s -i %s -m unarchive -a 'src=%s dest=%s copy=yes owner=tomcat group=tomcat backup=yes'" % (nodeName, ansibileHostFile, deployFile, deployDir)
    execSh(CopyZipFile)

def ansibleDirIsExists(ip,filepath):
    # 判断远程 文件或者目录是否存在
    cmd = "ansible %s -m stat -a 'path=%s' -o " % (ip, filepath)
    stdout, stederr = execSh(cmd)
    reslust = parseAnsibleOut(stdout)

    if reslust:
        print "%s 已经存在:%s" % (filepath,ip)
        return True
    elif reslust == None:
        print "%s 其他错误在: %s " % (filepath, ip)
        return None
    else:
        print "%s 不存在: %s " % (filepath, ip)
        return False

#检查文件是否存在
def fileExists(filePath):
    if not os.path.exists(filePath):
        print "文件：%s 不存在，请检查" % filePath
        return False
    return True

def readYml(file):
    with open(file) as fd:
       res = yaml.safe_load(fd)
    return res

# 初始化项目主应用可用于php部署，
def initProject(serverName):
    # 新机器 或者新目录项目部署
    print "master install:%s" % serverName
    # print projectDict
    builddir = projectDict[serverName]["buildDir"]
    if not os.path.exists(builddir):
        os.makedirs(builddir)
    try:
        gitUrl = projectDict[serverName]["giturl"]
    except:
        pass
    if not gitUrl:
        return False

    if not os.path.exists(builddir):
        os.mkdir(builddir)
    os.chdir(builddir)
    print "部署路径：", os.getcwd()
    stdout, stderr = execSh("git status .")
    if stdout:
        print"out：\n%s" % stdout
        print "当前目录：%s,已经存在git仓库请检查!" % builddir
        return True
    if stderr:
        print "没有git仓库，下一步"
        print"out：%s" % stderr

    print "初始化本地仓库"
    execSh("git init")

    print"本地git仓库当前项目认证"
    config_cmd = "git config --local credential.helper store"
    execSh(config_cmd)

    print "拉取代码"
    pull_cmd = "git pull %s" % gitUrl
    execSh(pull_cmd)

    print "添加远程仓库地址"
    add_remote_cmd = "git remote add origin %s" % gitUrl
    execSh(add_remote_cmd)

    print "获取分支"
    fetch_cmd = "git fetch"
    execSh(fetch_cmd)

    print "关联本地master分支与远程master"
    upstream_cmd = "git branch --set-upstream-to=origin/master master"
    execSh(upstream_cmd)

    print "获取 最新master分支"
    pull_m_cmd = "git pull"
    execSh(pull_m_cmd)

def init(Dir,gitUrl,gitType,force):
    # 初始化 本地打包构建git仓库
    print("git:%s init:%s" % (Dir, gitUrl))
    if not os.path.exists(Dir):
        os.makedirs(Dir)
    if not os.path.exists(Dir):
        os.mkdir(Dir)
    os.chdir(Dir)
    print("部署路径：", os.getcwd())
    stdout, stderr = execSh("git status .")
    if stdout:
        print("out：\n%s" % stdout)
        print("当前目录：%s,已经存在git仓库请检查!" % Dir)
        if not force:
            print("强制重新初始化 使用 -f force")
            return False
        else:
            print ("切换工作目录至：'/' ")
            os.chdir("/")
            print("清理历史目录：%s" % Dir)
            shutil.rmtree(Dir)
            print ("重新建立目录：%s" % Dir)
            if not os.path.exists(Dir):
                os.mkdir(Dir)
            print("切换工作目录至：%s" % Dir)
            os.chdir(Dir)
            print("执行强制初始化")

    if stderr:
        print("没有git仓库，下一步")

    print("初始化本地仓库")
    execSh("git init")

    # git url 使用http 协议的时候使用该命令 避免输入用户名密码
    # 用 ssh协议 请注释该代码
    if gitType == "http":
        print("本地git仓库当前项目认证")
        config_cmd = "git config --local credential.helper store"
        execSh(config_cmd)
    print("拉取代码")
    pull_cmd = "git pull %s" % gitUrl
    execSh(pull_cmd)

    print("添加远程仓库地址")
    add_remote_cmd = "git remote add origin %s" % gitUrl
    execSh(add_remote_cmd)

    print("获取分支")
    fetch_cmd = "git fetch"
    execSh(fetch_cmd)

    print("关联本地master分支与远程master")
    upstream_cmd = "git branch --set-upstream-to=origin/master master"
    execSh(upstream_cmd)

def readStdin():
    input_str = raw_input("确认执行操作：Y/N")
    return input_str.strip().lower()

# 合并分支至master
def mergeBranch(serverName, branchName):
    builddir = projectDict[serverName]["builddir"]
    fetch_cmd = "git fetch origin %s" % branchName
    checkout_b_cmd = "git checkout %s" % branchName
    pull_cmd = "git pull"
    checkout_m_cmd = "git checkout master"
    merge_cmd = "git merge origin/%s" % branchName
    push_cmd = "git push origin master"
    try:
        print "切换工作目录"
        print builddir
        os.chdir(builddir)  # 切换工做目录
        print os.getcwd()
    except Exception, e:
        print e
        sys.exit()

    print "取分支"
    stdout, stderr = execSh(fetch_cmd)
    print stdout

    if "fatal" in stderr:
        print stderr
        print "检查分支 branchname:%s" % branchName
        sys.exit()

    # ReturnExec(fetch_cmd)
    # 更新分支
    print "更新本地 分支"
    execSh(pull_cmd)

    # 切换至master分支
    if not checkMaster():
        print "切换至master分支"
        execSh(checkout_m_cmd)
    # 更新master分支
    print "更新master分支"
    execSh(pull_cmd)

    # 合并分支至master
    print "是否合并分支至master"
    execSh(merge_cmd)

    # 提交合并的master 至源端git库
    # 需要加确认 文件修改，在判断是否推送源端
    print "是否提交合并的master 至源端git库"
    option = readStdin()
    if option != "y":
        sys.exit()
    execSh(push_cmd)

def sonar(serverName):
  # sonar.login = admin
  # sonar.password = admin
  #   cmd = "{mvn} -X sonar:sonar \
  #       -Dsonar.projectKey={serverName} \
  #       -Dsonar.projectName={serverName} \
  #       -Dsonar.host.url=http://192.168.0.64:9000 \
  #       -Dsonar.login=6439729faaae953c3b4d3a85c474ae36e028fbbc".format(serverName=serverName,mvn=mvn)

    cmd = "{mvn} -X sonar:sonar \
          -Dsonar.projectKey={serverName} \
          -Dsonar.projectName={serverName} \
          -Dsonar.host.url=http://192.168.254.26:9000 \
          -Dsonar.login=4dad21ab0f4af755ccc2a0fffe7650d9534ae08b".format(serverName=serverName, mvn=mvn)

    builddir = projectDict[serverName]["buildDir"]
    os.chdir(builddir)
    stdout, stderr = execSh(cmd)

    if "BUILD FAILURE" in stdout:
        #print "stdout:%s" % stdout
        return False
    elif "BUILD FAILURE" in stderr:
        #print "stderr:%s" % stderr
        return False
    else:
        return True

def addconfToWar(serverName,envName,typeName):
    serverNameDict = projectDict[serverName]
    serverDict = getDeploymentTomcatPath(serverName)
    if typeName == "svn":
        serverNameEnvConfDir = os.path.join(svnConfigDir, serverName, "sys-%s") % envName
    else:
         os.chdir(configDir)
         print "获取新配置"
         pull_m_cmd = "git pull"
         stdout, stderr = execSh(pull_m_cmd)
         # 判断是否有git 执行错误
         isNoErr(stdout, stderr)
         serverNameEnvConfDir = os.path.join(configDir, serverName, "sys-%s") % envName
    serverNameTargetDir = serverNameDict["targetDir"]
    serverNamebuildDir = serverNameDict["buildDir"]
    serverNameTarget = os.path.join(serverNamebuildDir,'target')
    war = serverNameDict["war"]
    serverSysConfigDir = os.path.join(serverNameTargetDir, "WEB-INF/classes/resouce/sys")

    if os.path.exists(serverSysConfigDir):
        # print "清理默认的sys目录"
        myloger(name=serverName, level="INFO", msg="清理默认的sys目录,删除%s" % serverSysConfigDir )
        shutil.rmtree(serverSysConfigDir)
    try:
        msg= "copy sysconfig Dir :%s to:%s" % (serverNameEnvConfDir, serverSysConfigDir)
        myloger(name=serverName, level="INFO", msg=msg)
        shutil.copytree(serverNameEnvConfDir, serverSysConfigDir)
    except Exception, e:
        print e, "dir is exists！"
        sys.exit(1)
    os.chdir(serverNameTargetDir)
    cmd = '%s -cvf %s *' % (jar, war)
    myloger(name=serverName, level="INFO", msg="重新封装打包")
    execSh(cmd)
    myloger(name=serverName, level="INFO", msg="重新封装打包完成")

def initConf(typeName):
    if not os.path.exists(configDir):
        os.mkdir(configDir)
    os.chdir(configDir)
    if typeName == "svn":
        svnConfInit()
    elif typeName == "jar":
        svnConfInit()
    else:
        init(configDir, configUrl, gitType="ssh", force=False)

def svnUpdate(serverName):
    msg = "update svn %s" % serverName
    myloger(serverName,msg=msg)
    serverNameDict = projectDict[serverName]
    buildDir = serverNameDict["buildDir"]
    svnUrl = serverNameDict["svnUrl"]
    # buildDir = serverNameDict["buildDir"]
    os.chdir(buildDir)
    svnCmd = "svn up"
    msg = "update svn from %s" % svnUrl
    myloger(serverName, msg=msg)
    execSh(svnCmd)

def svnProjectDict(serverName):
    #重构svn 相关配置目录
    serverNameDict = projectDict[serverName]
    buildDir = serverNameDict["buildDir"]
    svnUrl = serverNameDict["svnUrl"]
    war = serverNameDict["war"]
    targetDir = serverNameDict["targetDir"]
    projectDir = svnUrl.split("/")[-1]
    warDirTmp = war.split(buildDir)
    # print warDirTmp
    targetTmp = targetDir.split(buildDir)
    buildDir = os.path.join(buildDir, projectDir)
    war = os.path.join(warDirTmp[0], projectDir,warDirTmp[-1])
    targetDir = os.path.join(targetTmp[0],projectDir,targetTmp[-1])
    return {
        "war": war,
        "buildDir": buildDir,
        "targetDir": targetDir
    }

def svnInit(serverName):
    serverNameDict = projectDict[serverName]
    svnUrl = serverNameDict["svnUrl"]
    buildDir = serverNameDict["buildDir"]
    if not os.path.exists(buildDir):
        # os.mkdirs(buildDir)
        os.makedirs(buildDir)
    os.chdir(buildDir)
    cmd = "svn co {svnUrl} {dir}".format(svnUrl=svnUrl, dir=buildDir)
    svnco = "svn  --username {userName} --password {passWord} co {svnUrl} {dir}".format(userName=svnUserName, passWord=svnPassWord, svnUrl=svnUrl,
                                           dir=buildDir)
    execSh(svnco)

def svnUninstall(serverName):
    # 删除构建仓库重新检出代码
    serverNameDict = projectDict[serverName]
    svnUrl = serverNameDict["svnUrl"]
    buildDir = serverNameDict["buildDir"]
    if os.path.exists(buildDir):
        shutil.rmtree(buildDir)

def svnConfInit():
    if not os.path.exists(svnConfigDir):
        os.mkdir(svnConfigDir)
    svncheck = "svn status"
    # svnco = "svn co {svnUrl} {dir}".format(userName=svnUserName,passWord=svnPassWord,svnUrl=svnConfigUrl,dir=svnConfigDir)
    svnco = "svn --username {userName} --password {passWord} co {svnUrl} {dir}".format(userName=svnUserName,passWord=svnPassWord,svnUrl=svnConfigUrl,dir=svnConfigDir)
    # svnco = "svn --username {userName} --password {passWord} co  svn://192.168.253.13/运维/SYS-CONFIG /project/svn-sys-config".format(userName=svnUserName,passWord=svnPassWord,svnUrl=svnConfigUrl,dir=svnConfigDir)

    os.chdir(svnConfigDir)
    stdout, stderr = execSh(svncheck)
    execSh(svnco)

def listToStr(liststr):
    ipPortStr = ""
    for i in liststr:
        ipPortStr += "," + i
    return ipPortStr

def main(serverName,branchName,action,envName,version,typeName):
    serverNameDict = projectDict[serverName]
    ansibleHostDict = readConfAnsible(ansibleHost)
    nginxNode = "{envName}nginx".format(envName=envName)
    # if envName == "dev":
    #     deploynode = serverNameDict["devNodeName"][0]
    # if envName == "test":
    #     deploynode = serverNameDict["testNodeName"][0]
    # if envName == "pro":
    #     deploynode = serverNameDict["proNodeName"][0]
    deploynode = serverNameDict["{envName}NodeName".format(envName=envName)][0]
    iplist = ansibleHostDict[deploynode]

    if serverName == "xkj-job-admin":
        typeName = "jar"
    if action == "init":
        if typeName == "svn":
            # initConf(typeName)
            svnInit(serverName)

        # 主服务项目部署 用代码分支合并，mvn 构建，在主服务器上
        elif typeName == "jar":
            svnInit(serverName)
        else:
            initProject(serverName)
    elif action == "initssh":
        sshAddHost()
    elif action == "reinit":
        if typeName == "svn":
            svnUninstall(serverName)
            svnInit(serverName)
        elif typeName == "jar":
            svnUninstall(serverName)
            svnInit(serverName)
        # 主服务项目部署 用代码分支合并，mvn 构建，在主服务器上
        else:
            initProject(serverName)
    elif action == "merge":
        # 主服务项目合并分支至master
        mergeBranch(serverName, branchName)
    elif action == "install":
        # 用于远端机器部署项目
        if typeName == "jar":
            execAnsibleDir(serverName, action, envName)
        else:
            execAnsible(serverName,deploynode, action, envName,typeName)

    elif action == "asyncinstall":
        # 用于远端机器部署项目
        for ip in iplist:
            myloger(name=serverName, msg="注册：%s 服务 节点：%s" % (serverName, ip))
            if typeName == "jar":
                execAnsibleDir(serverName, "install", envName)
            else:
                if not execAnsible(serverName, ip, "install", envName, typeName):
                    sys.exit()
            myloger(name=serverName, msg="完成注册：%s 服务节点：%s" % (serverName, ip))

    elif action == "uninstall":
        # 用于远端机器部署项目
        if typeName == "jar":
            execAnsibleDir(serverName, action, envName)
        else:
            execAnsible(serverName,deploynode, action, envName,typeName)
    elif action == "reinstall":
        # 用于远端机器部署项目
        if typeName == "jar":
            execAnsibleDir(serverName, "uninstall", envName)
            execAnsibleDir(serverName, "install", envName)
        else:
            execAnsible(serverName,deploynode, action, envName,typeName)
    elif action == "changmen":
        # 用于批量远程修改tomcat 启动参数 不用重新部署
        execAnsible(serverName,deploynode, action, envName,typeName)
    elif action == "changxml":
        # 用于批量远程修改tomcat 服务参数启动参数 不用重新部署72
        execAnsible(serverName,deploynode, action, envName,typeName)

    elif action == "sync":
        # 用于同步配置文件到生产远端机器部署项目
        syncJarconf("activity", "/data/activity/jar-prod.conf", "/app/activity-test/jar.conf")
        syncJarconf("activity", "/data/activity/server-prod.conf", "/app/activity-test/server.conf")
        syncJarconf("activity", "/data/activity/JarService-prod.py", "/app/activity-test/JarService.py")
    elif action == "build":
        initConf(typeName)
        if not branchName:
            print"branchName must arg"
        buildMaven(serverName, branchName, typeName)

    elif action == "deploy":
        initConf(typeName)
        if not buildMaven(serverName, branchName,typeName):
            print "build False"
            sys.exit(1)
        execAnsible(serverName,deploynode, "stop", envName,typeName)
        execAnsible(serverName, deploynode,"back", envName,typeName)
        #清理部署root目录 历史部署文件
        if typeName != "jar":
            # execAnsible(serverName, "cleanroot", envName,typeName)
            execAnsible(serverName,deploynode, "delroot", envName,typeName)
            execAnsible(serverName, deploynode,"delwar", envName,typeName)
        # 部署新包至目标节点
        deploy_node(serverName, deploynode,typeName)
        # sys.exit()
        if not execAnsible(serverName,deploynode, "start", envName,typeName):
            sys.exit(1)
        # 图片工程开发调试使用此代码，重新构建 软连接 都真是图片目录。注意 图片工程tomcat 设置需要打开软链接资产
        if serverName == "xkj-upload":
            execAnsible(serverName,deploynode, "uploadresour", envName,typeName)
    elif action == "asyncdeploy":
        # initConf(typeName)
        # if not buildMaven(serverName, branchName, typeName):
        #     print("build False")
        #     sys.exit(1)
        http_port = serverNameDict["http_port"]
        try:
            url = serverNameDict["urlName"]
        except Exception as e:
            url =""
        ipPortlist = [i.encode()+":"+str(http_port) for i in iplist]
        ipPortlistTmp = copy.deepcopy(ipPortlist)
        for ip in iplist:
             myloger(name=serverName, msg="更新：%s 服务 节点：%s" %(serverName,ip))
             if url:
                 ipPort = "{ip}:{Port}".format(ip=ip,Port=http_port)
                 if len(ipPortlist) >= 2:
                     ipPortlist.remove(ipPort)
                     myloger(name=serverName, msg="移除服务：%s" % ipPort)
                     ipPortStr = listToStr(ipPortlist)
                     execAnsibleNg(serverName,nginxNode,url,"update",ipPortStr,configPath=nginxConfigPath,templatePath=nginxTemplatePath)
             execAnsible(serverName, ip, "stop", envName, typeName)
             execAnsible(serverName, ip, "back", envName, typeName)
             # 清理部署root目录 历史部署文件
             if typeName != "jar":
                 execAnsible(serverName, ip, "delroot", envName, typeName)
                 execAnsible(serverName, ip, "delwar", envName, typeName)
             # 部署新包至目标节点
             deploy_node(serverName,ip, typeName)
             if not execAnsible(serverName, ip, "start", envName, typeName):
                 sys.exit(1)
             # 图片工程开发调试使用此代码，重新构建 软连接 都真是图片目录。注意 图片工程tomcat 设置需要打开软链接资产
             if serverName == "xkj-upload":
                 execAnsible(serverName, ip, "uploadresour", envName, typeName)
             ipPortlist = copy.deepcopy(ipPortlistTmp)
             myloger(name=serverName, msg="完成更新：%s 服务 节点：%s" %(serverName,ip))
        if url:
             ipPortlistTmp = listToStr(ipPortlistTmp)
             myloger(name=serverName, msg="恢复nginx：%s 服务 节点：%s" % (serverName, ipPortlistTmp))
             execAnsibleNg(serverName, nginxNode, url, "update", ipPortlistTmp, configPath=nginxConfigPath,
                      templatePath=nginxTemplatePath)
    elif action == "send":
        initConf(typeName)
        if not buildMaven(serverName, branchName, typeName):
            print "build False"
            sys.exit(1)
        execAnsible(serverName,deploynode, "back", envName, typeName)
        execAnsible(serverName, deploynode,"delwar", envName, typeName)
        deploy_node(serverName,deploynode,typeName)

    elif action == "asyncrestart":
        http_port = serverNameDict["http_port"]
        try:
            url = serverNameDict["urlName"]
        except Exception as e:
            url = ""
        ipPortlist = [i.encode() + ":" + str(http_port) for i in iplist]
        ipPortlistTmp = copy.deepcopy(ipPortlist)
        for ip in iplist:
            myloger(name=serverName, msg="重启：%s 服务 节点：%s" %(serverName,ip))
            if url:
                ipPort = "{ip}:{Port}".format(ip=ip, Port=http_port)
                if len(ipPortlist) >=2:
                    ipPortlist.remove(ipPort)
                    myloger(name=serverName, msg="移除服务：%s" % ipPort)
                    ipPortStr = listToStr(ipPortlist)
                    execAnsibleNg(serverName, nginxNode, url, "update", ipPortStr, configPath=nginxConfigPath,
                              templatePath=nginxTemplatePath)
            execAnsible(serverName,ip, "stop", envName,typeName)
            if typeName != "jar":
                # execAnsible(serverName, "cleanroot", envName, typeName)
                execAnsible(serverName,ip, "delroot", envName, typeName)
            if not execAnsible(serverName, ip,"start", envName,typeName):
                sys.exit(1)
            # 图片工程开发调试使用此代码，重新构建 软连接 都真是图片目录。注意 图片工程tomcat 设置需要打开软链接资产
            if serverName == "xkj-upload":
                    execAnsible(serverName, ip,"uploadresour", envName, typeName)
            ipPortlist = copy.deepcopy(ipPortlistTmp)
            myloger(name=serverName, msg="完成重启：%s 服务节点：%s" %(serverName,ip))
        if url:
             ipPortlistTmp = listToStr(ipPortlistTmp)
             execAnsibleNg(serverName, nginxNode, url, "update", ipPortlistTmp, configPath=nginxConfigPath,
                      templatePath=nginxTemplatePath)
    elif action == "restart":
        execAnsible(serverName,deploynode, "stop", envName, typeName)
        if typeName != "jar":
            # execAnsible(serverName, "cleanroot", envName, typeName)
            execAnsible(serverName,deploynode, "delroot", envName, typeName)
        if not execAnsible(serverName,deploynode, "start", envName, typeName):
            sys.exit(1)
        # 图片工程开发调试使用此代码，重新构建 软连接 都真是图片目录。注意 图片工程tomcat 设置需要打开软链接资产
        if serverName == "xkj-upload":
            execAnsible(serverName, deploynode,"uploadresour", envName, typeName)
    elif action == "start":
        if typeName != "jar":
            # execAnsible(serverName, "cleanroot", envName, typeName)
            execAnsible(serverName,deploynode, "delroot", envName, typeName)
        if not execAnsible(serverName, deploynode,action, envName,typeName):
           sys.exit(1)

        # 图片工程开发调试使用此代码，重新构建 软连接 都真是图片目录。注意 图片工程tomcat 设置需要打开软链接资产
        if serverName == "xkj-upload":
               execAnsible(serverName,deploynode, "uploadresour", envName, typeName)

    elif action == "stop":
        execAnsible(serverName,deploynode, action, envName,typeName)
    elif action == "sonar":
        sonar(serverName)
    elif action == "back":
        execAnsible(serverName, deploynode,action, envName,typeName)
    elif action == "getback":
        execAnsible(serverName,deploynode, action, envName,typeName)
    elif action == "rollback":
        execAnsible(serverName, deploynode,action, envName,typeName,version)
        if serverName == "xkj-upload":
            execAnsible(serverName, deploynode,"uploadresour", envName, typeName)
    elif action == "status":
        return execAnsible(serverName,deploynode, action, envName,typeName)
    else:
        print "action just [install,init,back,rollback，getback，start,stop,restart]"
        sys.exit(1)

# 读取启动服务顺序文件
def readfile(file):
    if not os.path.exists(file):
        return False
    with open(file) as fd:
        for i in fd.readlines():
            if i:
                return [i.strip().split(":")[1], i.strip().split(":")[0]]
            return False

# 写启动服务顺序文件
def writhfile(file,info):
    if not os.path.exists(file):
        print file
        with open(file, 'w+') as fd:
            fd.write(info)
    else:
        with open(file, 'w+')as fd:
            fd.write(info)

# 清理启动服务顺序文件
def cleanfile(file):
    with open(file, 'w+') as fd:
        fd.write("")

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
                      default="svn",
                      help="-t typeName")
    parser.add_option("-b", "--branchName", action="store",
                      dest="branchName",
                      default="master",
                      help="-b branchName")
    options, args = parser.parse_args()
    return options, args

# 输出服务配置文件中的服务名
def printServerName(projectDict):
    sorted_dict ={}
    serverlist = sortedServerName(projectDict)
    for serverName in serverlist:
        print "可执行服务名：%s" % serverName

# 执行服务重新排序
def sortedServerName(projectDict):
    sorted_dict = {}
    for serName,sub_dict in projectDict.iteritems():
        sorted_dict[int(sub_dict["startNum"])] = serName
    return sorted_dict.values()

class myThread(threading.Thread):
    def __init__(self, threadID, name, q):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q
    def run(self):
        # print "Starting " + self.name
        myloger(name=self.name,level="INFO",msg="Starting " )
        process_data(self.name, self.q)
        # checkServer.checkApi()
        # checkApi(self.name)
        # print "Exiting " + self.name
        myloger(name=self.name,level="INFO",msg="Exiting ")

exitFlag = 0
# threadList = ["Thread-1", "Thread-2", "Thread-3"]
# threadNum = 3
# 设置0 不受限
queueNum = 0
queueLock = threading.Lock()
workQueue = Queue.Queue(queueNum)
threads = []
threadID = 1

def process_data(threadName, q):
    while not exitFlag:
        queueLock.acquire()
        if not workQueue.empty():
            serName = q.get()
            queueLock.release()
            myloger(name=serName,level="INFO",msg="%s processing %s" % (threadName, serName))
            main(serName, branchName, action, envName, version, typeName)
            # checkApi(serName)
            # checkPort("xkj-upload")
        else:
            queueLock.release()
        time.sleep(1)

if __name__ == "__main__":
    c ="ansible 192.168.253.15 -m synchronize -a 'src=/python_yek/ dest=/python_yek/ delete=yes rsync_opts=--exclude=\.*'"

    # serverconf = "server.conf"
    # serverconf = "/tmp/pycharm_project_651/python_project/serverConf.yml"
    # serverconf = "/data/init/serverConf.yml"
    serverconf = "/python_yek/serverConf.yml"
    svnUserName="guozhiquan"
    svnPassWord= "123456"
    confDict = readYml(serverconf)
    mvn = confDict["mvn"]
    remote_py = confDict["remotePy"]
    python = confDict["python"]
    makeNginxConf = confDict["makeNginxConf"]
    nginxTemplatePath = confDict["nginxTemplatePath"]
    nginxConfigPath = confDict["nginxConfigPath"]
    java = confDict["java"]
    jar = confDict["jar"]
    nohup = confDict["nohup"]
    deploymentAppDir = confDict["deploymentAppDir"]
    startConf = confDict["startServer"]
    ansibleHost = confDict["ansibileHost"]
    # warConf = confDict["warConf"]
    tomcatPrefix = confDict["tomcatPrefix"]
    global logsPath
    logsPath = confDict["logsPath"]
    # print logsPath
    bakDir = confDict["bakDir"]
    configUrl = confDict["configUrl"]
    configDir = confDict["configDir"]
    svnConfigUrl = confDict["svnConfigUrl"]
    svnConfigDir = confDict["svnConfigDir"]
    threadNum = confDict["ParallelNum"]
    options, args = getOptions()
    action = options.action
    version = options.versionId
    serverName = options.serverName
    branchName = options.branchName
    typeName = options.typeName
    envName = options.envName
    warConf = confDict["warConf"].format(env=envName)
    startConf = startConf.format(env=envName)
    makeNginxConf = confDict["makeNginxConf"]
    nginxTemplatePath = confDict["nginxTemplatePath"]
    nginxConfigPath = confDict["nginxConfigPath"].format(env=envName)
   # execSh(c) # 需要注销 开发环境同步节点
    # print "系统配置文件：%s" % warConf
    myloger(name=serverName, level="INFO", msg="系统配置文件：%s" % warConf)
    projectDict = readYml(warConf)
    if not action:
        print "参数执行操作 -a action [install,init,back,rollback，getback，start,stop,restart]"
        sys.exit(1)
    elif not serverName:
        print "参数服务名 -n servername "
        printServerName(projectDict)
        sys.exit(1)
    elif not envName:
        print "参数执行操作 -e envName [dev,test,pro]"
        sys.exit(1)
    else:
        sDict = {}
        if serverName == "all":
            if readfile(startConf):
                serName, point = readfile(startConf)
            else:
                point = 0
            serverlist = sortedServerName(projectDict)
            # # 从上次执行失败的位置开始执行
            # for serName in serverlist[int(point):]:
            #     ser_index = serverlist.index(serName)
            #     info = "%s:%s" % (ser_index, serName)
            #     writhfile(startConf, info)
            #     # print serName
            #     main(serName, branchName, action, envName, version, typeName)
            #     time.sleep(10)
            #####
            # 创建新线程
            # 针对特殊操作走多线程，其他操作还是正常串行

            if action not in ["deploy","build","send","sonar"]:
                for num in range(1, threadNum + 1):
                    tName = "Thread %s" % num
                    thread = myThread(threadID, tName, workQueue)
                    thread.start()
                    threads.append(thread)
                    # threadID += 1
                # 填充队列
                queueLock.acquire()
                for serName in serverlist[int(point):]:
                    if not projectDict[serName]["Parallel"]:
                        # print('projectDict[serName]["Parallel"]:',projectDict[serName]["Parallel"])
                        ser_index = serverlist.index(serName)
                        info = "%s:%s" % (ser_index, serName)
                        writhfile(startConf, info)
                        print "串行 %s" %serName
                        d = main(serName, branchName, action, envName, version, typeName)
                        print "d",d
                        # sDict.update(d)
                    else:
                        print "并行 %s" % serName
                        workQueue.put(serName)
                queueLock.release()
                # 等待队列清空
                while not workQueue.empty():
                    pass
                # 通知线程是时候退出
                exitFlag = 1
                # 等待所有线程完成
                for t in threads:
                    t.join()
                myloger(name="Main Thread",level="INFO",msg="Exiting Main Thread")
                "增加多线程"
                #####
                print sDict
            else:
                for serName in serverlist[int(point):]:
                    ser_index = serverlist.index(serName)
                    info = "%s:%s" % (ser_index, serName)
                    writhfile(startConf, info)
                    d = main(serName, branchName, action, envName, version, typeName)
                    sDict.update(d)
                    time.sleep(1)
            cleanfile(startConf)
        else:
            if not projectDict.has_key(serverName):
                print "没有服务名：%s" % serverName
                printServerName(projectDict)
                sys.exit(1)
            main(serverName, branchName, action, envName, version, typeName)