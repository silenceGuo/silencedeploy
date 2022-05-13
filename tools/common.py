#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 2020-11-6 下午 13:48 
# @Author : damon.guo 
# @File : common.py 
# @Software: PyCharm
import yaml
from subprocess import PIPE,Popen
from func_timeout import func_set_timeout
from concurrent.futures import ThreadPoolExecutor,as_completed
import func_timeout
import os
import sys
from optparse import OptionParser
import threading
import logging
import shutil
import datetime
import time
from tornado import template
from logging import handlers
# reload(sys)
# sys.setdefaultencoding('utf-8')
def readYml(confPath):
    with open(confPath) as fd:
        res = yaml.safe_load(fd)
    return res

def myloger(name="debugG", logDir="/tmp", level="INFO", msg="default test messages"):
    logPath = os.path.join(logDir, "logger2")
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

def execSh(serverName,cmd, print_msg=True):
    # 执行SH命令
    stdout_lines = ""
    stderr_lines = ""
    try:
        myloger(name=serverName, level="INFO", msg="执行命令开始 exec shell:>>%s<<" % cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        if p.stdout:
            for line in iter(p.stdout.readline, b''):
                line = line.rstrip().decode('utf8')
                if print_msg:
                    myloger(name=serverName, msg=line)
                else:
                    print(line)
                stdout_lines += line+"\n"
        if p.stderr:
            for err in iter(p.stderr.readline, b''):
                err = err.rstrip().decode('utf8')
                if print_msg:
                    myloger(name=serverName, level="ERROR", msg=err)
                else:
                    print(err)
                stderr_lines += err+"\n"
        p.wait()
        myloger(name=serverName, level="INFO", msg="执行命令结束 exec shell:>>%s<<" %cmd)
    except Exception as e:
        myloger(name=serverName, level="ERROR", msg="错误信息:>>%s<<" % e)
    return stdout_lines, stderr_lines

def dir_is_null(path):
    # print os.listdir(path)
    if os.path.exists(path):
        if os.listdir(path):
            # 不为空 False
            return False
    # 是空返回True
    return True

def execShSmall(cmd):
    # 执行SH命令
    try:
        print("执行ssh命令 %s" % cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    except Exception as e:
        print(e)
        sys.exit()
    stdout,stderr = p.communicate()
    stdout = str(stdout, encoding='utf-8')
    stderr = str(stderr, encoding='utf-8')
    # return p.communicate()
    return stdout,stderr


def printServerName(projectDict):
    serverlist = sortedServerName(projectDict)
    for serverName in serverlist:
        myloger(name="console", msg="可执行服务名：%s" % serverName)

def sortedServerName(serverDict):
    sorted_dict = {}
    sorted_list =[]
    for serName, sub_dict in serverDict.items():
        sorted_dict[int(sub_dict["startNum"])] = serName
    for i in sorted(sorted_dict):
        sorted_list.append(sorted_dict[i])
    return sorted_list

def readFile(file):

    myloger(name="read", msg="读文件%s" % file)
    if not os.path.exists(file):
        return False
    info = ""
    with open(file, 'rb') as fd:
        for i in fd.readlines():
            try:
                info += i.decode("utf-8", errors='ignore')
            except Exception as e:
                print(e)
                info += i
    return info
# 读取启动服务顺序文件
def readfile(file):
    if not os.path.exists(file):
        return False
    with open(file) as fd:
        for i in fd.readlines():
            if i:
                return [i.strip().split(":")[1], i.strip().split(":")[0]]
            return False

def copyFile(serverName,sourfile,disfile):
    try:
        myloger(name=serverName, msg="复制文件:%s,to:%s" % (sourfile, disfile))
        shutil.copy2(sourfile, disfile)  # % ( disfile, time.strftime("%Y-%m-%d-%H%M%S"))
    except Exception as e:
        myloger(name=serverName, msg="err:%s" % e)
        sys.exit(1)

def copyDir(serverName,sourfile,disfile):
    try:
        myloger(name=serverName, msg="复制目录:%s,to:%s" % (sourfile, disfile))
        shutil.copytree(sourfile, disfile)  # % ( disfile, time.strftime("%Y-%m-%d-%H%M%S"))
    except Exception as e:
        myloger(name=serverName, msg="err:%s" % e)
        sys.exit(1)

# 写启动服务顺序文件
def writhfile(file,info):
    absdir = os.path.abspath(os.path.join(file,"../"))
    if not os.path.exists(absdir):
        os.makedirs(absdir)
    if not os.path.exists(file):
        with open(file, 'w') as fd:
            fd.write(info)
        return file
    else:
        with open(file, 'w+')as fd:
            fd.write(info)
        return file

# 写启动服务顺序文件
def writhfileb(file,info):
    if not os.path.exists(file):
        with open(file, 'wb') as fd:
            fd.write(info)
        return file
    else:
        with open(file, 'wb')as fd:
            fd.write(info)
        return file

def writeYml(file,statusDict):
    # 目前主要用于新增服务的初始化
    with open(file, 'w+')as fd:
        yaml.dump(statusDict, fd)
    msg = "write in %s" % file
    myloger(msg=msg)

def threadPool(arglist,threadNum,main,*args):
    #线程池
    tpool = []
    with ThreadPoolExecutor(max_workers=threadNum, thread_name_prefix="test_") as threadPool:
        for ag in arglist:
            obj = threadPool.submit(main, ag, *args)
            tpool.append(obj)
            myloger(name=ag, msg="多线程执行:%s，并发线程数:%s" % (ag, threadNum))
        for future in as_completed(tpool):
            name = threading.current_thread().name
            myloger(name=name, msg="线程执行完成!")


def threadPool2(arglist,threadNum,main,*args):
    #线程池
    tpool = []
    with ThreadPoolExecutor(max_workers=threadNum, thread_name_prefix="test_") as threadPool:
        threadPool.map(main, arglist, *args)
        myloger(name="ss", msg="线程执行中!")


def result(resultYml,serverName):
    if os.path.exists(resultYml):
        statusDict = readYml(resultYml)
        if serverName not in statusDict.keys():
            statusDict[serverName] = {}
    else:
        statusDict = {}
        statusDict[serverName] = {}
    dateNow = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
    statusDict[serverName]["timestamps"] = dateNow
    return statusDict

def writeResult(resultYml,envName,serverName,kubectl,kubeconfig):
    statusDict = result(resultYml, serverName)
    try:
        res = checkDeployStatus(serverName, kubectl, envName, kubeconfig)
        statusDict[serverName]["deployResult"] = res
        writeYml(resultYml, statusDict)
    except func_timeout.exceptions.FunctionTimedOut:
        myloger(name=serverName,
                msg="部署服务:%s 检查服务更新状态超时！" % (serverName))
        statusDict[serverName]["deployResult"] = "timeout"
        writeYml(resultYml, statusDict)

def showResult(resultYml,action,serverName):
    if os.path.exists(resultYml):
        serverDict = readYml(resultYml)
        sortlist = serverDict.keys()
    else:
        return
    if serverName == "all":
        for ser in sortlist:
            if action =="build":
                myloger(name=ser, msg="""
                构建服务结果输出:{serverName}
                时间:{result[timestamps]}
                构建结果:{result[buildMavenResult]}
                ###############################""".format(serverName=ser,result=readYml(resultYml)[ser]))
            elif action == "deploy" or action == "redeploy":
                myloger(name=ser, msg="""
                构建服务结果输出:{serverName}
                时间:{result[timestamps]}
                部署结果:{result[deployResult]}
                ###############################""".format(serverName=ser,result=readYml(resultYml)[ser]))
            else:
                pass
    else:
        if action == "build":
            myloger(name=serverName, msg="""
            构建服务结果输出:{serverName}
            时间:{result[timestamps]}
            构建结果:{result[buildMavenResult]}
            ###############################""".format(serverName=serverName, result=readYml(resultYml)[serverName]))
        elif action == "deploy" or action == "redeploy":
            myloger(name=serverName, msg="""
            构建服务结果输出:{serverName}
            时间:{result[timestamps]}
            部署结果:{result[deployResult]}
            ###############################""".format(serverName=serverName, result=readYml(resultYml)[serverName]))
        else:
            pass


def genConfigFile(serverName,dataDict,tmp,outfile):
    ret = genConfigString(dataDict, tmp)
    myloger(name=serverName, msg="生成%s ,配置文件;%s" % (serverName, outfile))
    fp_config = open(outfile, 'wb')
    fp_config.write(ret)
    fp_config.close()

def pkill(keys):
    myloger("kill",msg="请谨慎使用,是批量kill 进程")
    cmd = "ps -aux| grep {keys}".format(keys=keys)
    stdout, stderr = execSh("pkill",cmd)
    myloger("get进程", msg="请谨慎使用,核对进程!")
    input_str = raw_input("确认是否执行操作Y/N：")
    input_str = input_str.strip().lower()
    if input_str == "y":
        cmd = "kill -s 9 `ps -aux | grep %s | awk '{print $2}'`" % keys
        stdout, stderr = execSh("pkill", cmd)
    else:
        myloger("kill进程", msg="已取消操作")

def genConfigString(dataDict,tmp):
    loader = template.Loader(tmp)
    ret = loader.load(tmp).generate(**dataDict)
    return ret


def genTmpFile(serverName,dataDict,tmp,outfile):
    
    ret = genConfigString(dataDict, tmp)
    myloger(name=serverName, msg="应用:{serverName},使用模板:{Tmp} 生成文件:{outfile}".format(
        Tmp=tmp, serverName=serverName,outfile=outfile))
    writhfileb(outfile, ret)

def desDeployStatus(serverName,kubectl,envName,kubeconfig):
   # 通过判断OldReplicaSets 是否存在，存在还在更新中，不在存说明已经更新完成
   stdout,stderr = execSh(serverName,
                  "{kubectl} --kubeconfig {kubeconfig} describe deployment/{serverName}-{envName} -n {envName}".format(
                      kubectl=kubectl,
                      serverName=serverName, envName=envName,kubeconfig=kubeconfig))
   return parseDesDeployStatusOut(stdout,serverName, kubectl, envName, kubeconfig)

def getDeployStatus(serverName,kubectl,envName,kubeconfig):
   # 通过判断OldReplicaSets 是否存在，存在还在更新中，不在存说明已经更新完成
   stdout,stderr = execSh(serverName,
                  "{kubectl} --kubeconfig {kubeconfig} get deployment/{serverName}-{envName} -n {envName}".format(
                      kubectl=kubectl,
                      serverName=serverName, envName=envName,kubeconfig=kubeconfig))
   return parseGetDeployStatusOut(stdout)

def parseGetDeployStatusOut(stdout):
    if stdout:
        lines = stdout.split("\n")
        status = [i.strip() for i in lines[1].split(" ") if i]
        statusNum = int(status[3])
        if statusNum > 0:
            return True
        return False


def parseDesDeployStatusOut(stdout,serverName, kubectl, envName, kubeconfig):
    statusDict={}
    if stdout:
        lines = stdout.split("\n")
        status = [i.strip() for i in lines if i.startswith("OldReplicaSets") or i.startswith("NewReplicaSet")]
        events = [i.strip("") for i in lines if i.strip().startswith("Normal")]
        eventslen=len(events)
        for i in status:
            name, key = i.split(":")
            statusDict[name] = key.strip()
        if eventslen == 1:
            if statusDict["OldReplicaSets"] == "<none>":
                # 对于还未重新部署过的服务，要增加可用pod检查，否则会一直卡住，
                if getDeployStatus(serverName, kubectl, envName, kubeconfig):
                    return True
                return False
        else:
            if statusDict["OldReplicaSets"] == "<none>":
                return True
            return False
# 超时120s
@func_set_timeout(180)
def checkDeployStatus(serverName,kubectl,envName,kubeconfig):
    while True:
        myloger(name=serverName, msg="检查服务状态:%s,环境:%s" % (serverName, envName))
        if desDeployStatus(serverName,kubectl,envName,kubeconfig):
            # pass
            myloger(name=serverName, msg="检查服务状态:%s,环境:%s,启动完成！" % (serverName, envName))
            return True
        time.sleep(5)

def cleanDir(path):
    if not os.path.exists(path):
        print("Is not exit dir/file: %s" % path)
    if not os.path.isfile(path):
       try:
           shutil.rmtree(path)
           print("clean dir: %s" % path)
       except Exception as e:
           print(e)
    else:
        os.remove(path)
        print("clean  file: %s " % path)


def getip():
    stdout, stderr = execShSmall("ip a")
    ipstr = [i.strip() for i in stdout.split("\n") if i.strip().startswith("inet 192.168.")]
    for i in ipstr:
        if "eth" in i or "eno" in i:
            iplist = i.split(" ")
            for ips in iplist:
                if ips.startswith("192.168.") and not ips.endswith("255"):
                    ip = ips.split("/")[0]
    if ip:
        print("获取节点ip：%s" % ip)
        return ip
    else:
        print("未获取节点ip 请检查" )
        return "192.168.0.2"

def sonar(serverName,mvn,masterDir):
    cmd = "{mvn} -X sonar:sonar \
          -Dsonar.projectKey={serverName} \
          -Dsonar.projectName={serverName} \
          -Dsonar.host.url=http://sonar.xiaokangjun.com \
          -Dsonar.login=xxx".format(serverName=serverName, mvn=mvn)
    os.chdir(masterDir)
    stdout, stderr = execSh(serverName,cmd)
    if "BUILD FAILURE" in stdout:
        return False
    elif "BUILD FAILURE" in stderr:
        return False
    else:
        return True

def Gitinit(serverName,gitUrl,masterDir):
        myloger(name=serverName, msg="master install:%s" % serverName)
        myloger(name=serverName, msg="初始化本地仓库 install:%s" % serverName)
        if not os.path.exists(masterDir):
            os.makedirs(masterDir)
        os.chdir(masterDir)
        myloger(name=serverName, msg="deploy path:%s" % os.getcwd())
        stdout, stderr = execSh(serverName,"git status .")
        if "On branch" in stdout:
            myloger(name=serverName, msg=u"out:%s" % stdout)
            myloger(name=serverName, msg="当前目录：%s,已经存在git仓库请检查!" % masterDir)
            sys.exit()
            return False
        if "fatal: Not a git repository" in stderr:
            myloger(name=serverName, msg="没有git仓库，下一步")
            myloger(name=serverName, msg=u"stderr:%s" % stderr)
        myloger(name=serverName, msg="初始化本地仓库")
        execSh(serverName,"git init")

        myloger(name=serverName, msg="本地git仓库当前项目认证")
        config_cmd = "git config --local credential.helper store"
        config_cmd2 ="git config --global push.default simple"
        execSh(serverName,config_cmd)
        execSh(serverName,config_cmd2)

        myloger(name=serverName, msg="拉取代码%s" % gitUrl)
        pull_cmd = "git pull %s" % gitUrl
        execSh(serverName,pull_cmd)

        myloger(name=serverName, msg="添加远程仓库地址%s" % gitUrl)
        add_remote_cmd = "git remote add origin %s" % gitUrl
        execSh(serverName,add_remote_cmd)

        myloger(name=serverName, msg="获取分支")
        fetch_cmd = "git fetch"
        execSh(serverName,fetch_cmd)

        myloger(name=serverName, msg="关联本地master分支与远程master")
        upstream_cmd = "git branch --set-upstream-to=origin/master master"
        execSh(serverName,upstream_cmd)

        myloger(name=serverName, msg="获取最新master分支")
        pull_m_cmd = "git pull"
        execSh(serverName,pull_m_cmd)
        return True

# 清理启动服务顺序文件
def cleanfile(file):
    with open(file, 'w+') as fd:
        fd.write("")

def TimeStampToTime(timestamp):
    # 时间戳转换为时间
    timeStruct = time.localtime(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S', timeStruct)

def getTimeStamp(filePath):
    # pthon2
    # filePath = unicode(filePath, 'utf8')
    #pthon3
    filePath = str(filePath)
    t = os.path.getmtime(filePath)
    # return t
    return TimeStampToTime(t)
def getOptions():
    date_now = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
    parser = OptionParser()
    parser.add_option("-n", "--serverName", action="store",
                      dest="serverName",
                      default=False,
                      help="serverName to do")
    parser.add_option("-a", "--action", action="store",
                      dest="action",
                      default=False,
                      help="action -a [checkout,pull,push,master,install]")

    parser.add_option("-v", "--versionId", action="store",
                      dest="versionId",
                      default=date_now,
                      help=" -v versionId defalut datetime [%Y-%m-%d-%H-%M:2019-03-06-16-05]")
    parser.add_option("-b", "--branchName", action="store",
                      dest="branchName",
                      default=False,
                      help="-b branchName")
    parser.add_option("-m", "--mbranchName", action="store",
                      dest="mbranchName",
                      default=False,
                      help="-m mbranchName")
    # jar 服务启动区分环境 读取的配置不一样 这里与k8s的名称空间是联动的
    parser.add_option("-e", "--envName", action="store",
                      dest="envName",
                      default="default",
                      help="-e envName")
    parser.add_option("-t", "--typeName", action="store",
                      dest="typeName",
                      default="default",
                      help="-t typeName")
    # 项目名称，-n 则设定为项目中的名称
    parser.add_option("-p", "--projectName", action="store",
                      dest="projectName",
                      default="k8s",
                      help="-p projectName")
    # 配置文件
    parser.add_option("-f", "--configFile", action="store",
                      dest="configFile",
                      default="config.yaml",
                      help="-f configFile")
    options, args = parser.parse_args()
    return options, args

if __name__ == "__main__":
    pkill("vim")
    pass