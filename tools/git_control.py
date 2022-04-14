#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 2020-9-28 上午 10:35 
# @Author : damon.guo 
# @File : Gitinitv2.py 
# @Software: PyCharm
import yaml
from subprocess import PIPE,Popen
import os
import sys
import threading
import logging
import shutil
import datetime
from logging import handlers
# import tools.common
from tools import common
# import tools.common

# @pysnooper.snoop()
class git():
    def __init__(self,confPath,serverName):
        # Option = Options()
        options, args = common.getOptions()
        self.envName = options.envName
        self.serverName = serverName
        self.confPath = confPath
        self.serverDict = common.readYml(self.confPath)
        if self.serverName not in self.serverDict:
            common.myloger(name=self.serverName, msg="%s is not in %s,please check!" % (self.serverName, self.confPath))
            sys.exit(1)
        serverNameDict = self.serverDict[self.serverName]
        self.masterDir = serverNameDict["git"]["masterDir"].format(envName=self.envName)
    def init(self):
        common.myloger(name=self.serverName, msg="master install:%s" % self.serverName)
        common.myloger(name=self.serverName, msg="初始化本地仓库 install:%s" % self.serverName)
        serverNameDict = self.serverDict[self.serverName]
        if not os.path.exists(self.masterDir):
            os.makedirs(self.masterDir)
        try:
            gitUrl = serverNameDict["git"]["gitUrl"]
        except Exception as e:
            print(e)
            common.myloger(name=self.serverName, msg="异常:%s" % e)
            return False
        os.chdir(self.masterDir)
        common.myloger(name=self.serverName, msg="deploy path:%s" % os.getcwd())
        stdout, stderr = common.execSh(self.serverName,"git status .")
        if "On branch" in stdout:
            common.myloger(name=self.serverName, msg=u"out:%s" % stdout)
            common.myloger(name=self.serverName, msg="当前目录：%s,已经存在git仓库请检查!" % self.masterDir)
            sys.exit()
            return False
        if "fatal: Not a git repository" in stderr:
            common.myloger(name=self.serverName, msg="没有git仓库，下一步")
            common.myloger(name=self.serverName, msg=u"stderr:%s" % stderr)
        common.myloger(name=self.serverName, msg="初始化本地仓库")
        common.execSh(self.serverName,"git init")

        common.myloger(name=self.serverName, msg="本地git仓库当前项目认证")
        config_cmd = "git config --local credential.helper store"
        config_cmd2 ="git config --global push.default simple"
        config_cmd3 ="git config --global http.postBuffer 242880000"
        common.execSh(self.serverName,config_cmd)
        common.execSh(self.serverName,config_cmd2)
        common.execSh(self.serverName,config_cmd3)

        common.myloger(name=self.serverName, msg="拉取代码%s" % gitUrl)
        pull_cmd = "git pull %s" % gitUrl
        # pull_cmd = "git clone %s" % gitUrl
        common.execSh(self.serverName,pull_cmd)

        common.myloger(name=self.serverName, msg="添加远程仓库地址%s" % gitUrl)
        add_remote_cmd = "git remote add origin %s" % gitUrl
        common.execSh(self.serverName,add_remote_cmd)

        common.myloger(name=self.serverName, msg="获取分支")
        fetch_cmd = "git fetch"
        common.execSh(self.serverName,fetch_cmd)

        common.myloger(name=self.serverName, msg="关联本地master分支与远程master")
        upstream_cmd = "git branch --set-upstream-to=origin/master master"
        common.execSh(self.serverName,upstream_cmd)

        common.myloger(name=self.serverName, msg="获取最新master分支")
        pull_m_cmd = "git pull"
        common.execSh(self.serverName,pull_m_cmd)
        return True

    def checkBranch(self, masterBranch):
        # 获取项目分支是否为master
        common.myloger(name=self.serverName, msg="检查当前分支：%s " % masterBranch)
        os.chdir(self.masterDir)
        cmd = "git branch"
        stdout, stderr = common.execSh(self.serverName,cmd)
        branch_list = [i.strip() for i in stdout.split("\n") if i]
        print(branch_list)
        branchName_str = "* %s" % masterBranch
        if branchName_str in branch_list[0]:
            common.myloger(name=self.serverName, msg="当前分支：%s " % masterBranch)
            return True
        return False

    def branchExist(self,masterBranch):
        # 获取项目分支是否为master
        cmd = "git branch"
        stdout, stderr = common.execSh(self.serverName,cmd)
        # branch_list = [i.strip() for i in stdout.split("\n") if i][0].split(" ")
        branch_list = [i.strip() for i in stdout.split("\n")]
        # branchName_str = "* %s" % branchName
        branchName_str = "%s" % masterBranch
        if branchName_str in branch_list:
            common.myloger(name=self.serverName, msg="%s 分支已经存在" % masterBranch)
            return True
        return False

    def readStdin(self):
        input_str = raw_input("确认执行操作：Y/N")
        return input_str.strip().lower()

    def merge(self, branchName,masterBranch):
        # if branchName == masterBranch == "master":
        # checkout_b_cmd = "git checkout %s" % branchName
        common.myloger(name=self.serverName, msg="合并分支：%s 至 %s" % (branchName, masterBranch))
        try:
            common.myloger(name=self.serverName, msg="切换工作目录")
            os.chdir(self.masterDir)  # 切换工做目录
        except Exception as e:
            print(e)
            return False
        common.execSh(self.serverName,"git pull")
        common.execSh(self.serverName,"git checkout %s" % branchName)
        common.myloger(name=self.serverName, msg="取分支:%s" % branchName)
        fetch_cmd = "git fetch origin %s" % branchName
        stdout, stderr = common.execSh(self.serverName, fetch_cmd)
        if "fatal" in stderr or "error" in stderr:
            self. myloger(name=self.serverName, msg="stderr:%s" % stderr)
            common.myloger(name=self.serverName, msg="请检查分支 branchname:%s" % branchName)
            return False
        # ReturnExec(fetch_cmd)
        common.myloger(name=self.serverName, msg="更新本地分支")
        pull_cmd = "git pull"
        common.execSh(self.serverName, pull_cmd)
        # 切换至master分支
        # if not self.checkBranch(m_branch):
        common.myloger(name=self.serverName, msg="切换至%s分支 " % masterBranch)
        checkout_m_cmd = "git checkout %s" % masterBranch
        stdout,stderr = common.execSh(self.serverName,checkout_m_cmd)
        if "pathspec '%s' did not match" % masterBranch in stderr:
            common.myloger(name=self.serverName, msg="分支：%s 不存在 " % masterBranch)
            return False
        common.myloger(name=self.serverName, msg="更新%s分支" % masterBranch)
        common.execSh(self.serverName,pull_cmd)
        common.myloger(name=self.serverName, msg="是否合并分支：%s 至%s" % (branchName, masterBranch))
        merge_cmd = "git merge %s" % branchName
        stdout, stderr = common.execSh(self.serverName,merge_cmd)
        if "Merge conflict" in stderr:
            common.myloger(name=self.serverName, msg="合并分支：%s 至 %s,存在冲突！" % (branchName, masterBranch))
            return False
        # 提交合并的master 至源端git库
        # 需要加确认 文件修改，在判断是否推送源端
        # common.myloger(name=self.serverName, msg="是否提交合并的%s至远端git库" % masterBranch)
        # option = self.readStdin()
        # if option != "y":
        #     common.myloger(name=self.serverName, msg="取消分支合并：%s" % self.serverName)
        #     return False
        push_cmd = "git push"
        common.execSh(self.serverName,push_cmd)
        return True

    def reinit(self):
        common.myloger(name=self.serverName, msg="重新初始化：%s" % self.serverName)
        if os.path.exists(self.masterDir):
            common.myloger(name=self.serverName, msg="删除原仓库目录：%s" % self.masterDir)
            shutil.rmtree(self.masterDir)
        self.init()
        return True

    def pull(self, masterBranch):
        common.myloger(name=self.serverName, msg="更新分支:%s," % masterBranch)
        common.myloger(name=self.serverName, msg="切换工作目录:%s," % self.masterDir)
        os.chdir(self.masterDir)
        common.myloger(name=self.serverName, msg="拉取远端分支")
        common.execSh(self.serverName,"git fetch")
        common.myloger(name=self.serverName, msg="切换分支:%s" % masterBranch)
        checkout_b_cmd = "git checkout %s" % masterBranch
        stdout, stderr = common.execSh(self.serverName,checkout_b_cmd)
        if "did not match any file(s) known to git" in stderr:
            common.myloger(name=self.serverName, msg="分支:%s 错误，请检查！" % masterBranch)
            return False
        common.myloger(name=self.serverName, msg="更新分支:%s," % masterBranch)
        pull_cmd = "git pull"
        common.execSh(self.serverName,pull_cmd)
        return True

    def push(self,branchName):
        try:
            common.myloger(name=self.serverName, msg="切换工作目录")
            os.chdir(self.masterDir)  # 切换工做目录
        except Exception as e:
            print(e)
            return False
        common.myloger(name=self.serverName, msg="更新%s分支" % branchName)
        # common.execSh(self.serverName, pull_cmd)
        common.execSh(self.serverName, "git add .")
        common.execSh(self.serverName, "git commit -m 'cmdpush'")
        common.execSh(self.serverName, "git push")
        return True


    def createBranch(self,masterBranch,branchName):
        common.myloger(name=self.serverName, msg="从分支:%s 新建分支%s,并且切换" % (masterBranch,branchName))
        checkout_b_cmd = "git checkout -b %s" % branchName
        push_cmd = "git push origin %s -u" % branchName
        os.chdir(self.masterDir)
        common.execSh(self.serverName,"git checkout %s" % masterBranch)
        common.myloger(name=self.serverName, msg="新建分支%s,并且切换" % branchName)
        stdout, stderr = common.execSh(self.serverName,checkout_b_cmd)
        if "fatal: A branch named '%s' already exists" % branchName in stderr:
            common.myloger(name=self.serverName, msg="分支%s,已经存在！" % branchName)
            return False
        common.myloger(name=self.serverName, msg="关联远程分支%s,并提交" % branchName)
        stdout, stderr = common.execSh(self.serverName,push_cmd)
        return True

    def deleteBranch(self,masterBranch,branchName):
        if branchName == "master":
            common.myloger(name=self.serverName, msg="删除分支:%s 不允许！！" % branchName)
            return False
        os.chdir(self.masterDir)
        common.myloger(name=self.serverName, msg="删除分支:%s" % branchName)
        common.execSh(self.serverName,"git checkout %s" % masterBranch)
        common.myloger(name=self.serverName, msg="删除本地分支%s！" % branchName)
        stdout, stderr = common.execSh(self.serverName,"git branch -d %s" % branchName)
        if "branch '%s' not found" % branchName in stderr:
            common.myloger(name=self.serverName, msg="分支%s,不存在！" % branchName)
            return True
        common.myloger(name=self.serverName, msg="删除远端分支%s！" % branchName)
        common.execSh(self.serverName,"git push origin --delete %s" % branchName)
        return True

    def revert(self, masterBranch,commitId):
        commitDict = self.getCommitList(masterBranch)
        date_now = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
        if not self.pull(masterBranch):
            return False
        config_cmd = 'git config --global user.email "jenkins@example.com"'
        config_cmd2 = 'git config --global user.name "jenkins"'
        common.execSh(self.serverName,config_cmd)
        common.execSh(self.serverName,config_cmd2)
        if commitId and commitDict.has_key(commitId):
            common.myloger(name=self.serverName, msg="分支%s,版本回退指定版本:%s,且提交远程" % (masterBranch,commitId))
            common.execSh(self.serverName,"git revert HEAD -n %s" % commitId)  # 回退到上一个版本
            common.execSh(self.serverName,"git commit -m 'rollback commit:%s'" % commitId)
        # elif not commitDict.has_key(commitId):
        #     common.myloger(name=self.serverName, msg="分支%s,版本回退指定版本:%s,错误" % (masterBranch, commitId))
        #     return False
        else:
            common.myloger(name=self.serverName, msg="分支%s,版本回退上一个版本,且提交远程" % masterBranch)
            common.execSh(self.serverName,"git revert HEAD -n")  # 回退到上一个版本
        common.execSh(self.serverName,"git push")

    def getCommitList(self, masterBranch):
        os.chdir(self.masterDir)
        if not masterBranch:
            common.myloger(name=self.serverName, msg="获取分支%s,历史版本commitid 错误" % (masterBranch))
            return False
        common.myloger(name=self.serverName, msg="获取分支%s,历史版本commitid" % (masterBranch))
        common.execSh(self.serverName,"git checkout %s" % masterBranch)
        common.execSh(self.serverName,"git pull")  # 回退到上一个版本
        stdout,stderr = common.execSh(self.serverName,"git log -10")  # 获取最新10个版本
        commitList = stdout.split("commit")
        commitDict = {}
        for i in commitList:
            if i.strip():
                sublist = [j.strip() for j in i.strip().split("\n") if j]
                commitDict[sublist[0]] = sublist[1:]
        # print(commitDict)
        return commitDict


# if __name__ == "__main__":
#     ConfPATH = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
#     g = git(ConfPATH, "express-admin")
#     # g.reinit()
#     print(g.serverName)
