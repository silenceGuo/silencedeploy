#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 2020-9-28 上午 10:35 
# @Author : damon.guo 
# @File : Gitinitv2.py 
# @Software: PyCharm
from tools.common import *
# @pysnooper.snoop()
class git():
    def __init__(self,confPath,serverName):
        options, args = getOptions()
        self.envName = options.envName
        self.serverName = serverName
        self.confPath = confPath
        self.serverDict = readYml(self.confPath)
        if self.serverName not in self.serverDict:
            myloger(name=self.serverName, msg="%s is not in %s,please check!" % (self.serverName, self.confPath))
            sys.exit(1)
        serverNameDict = self.serverDict[self.serverName]
        self.masterDir = serverNameDict["git"]["masterDir"].format(envName=self.envName)
    def init(self,serverName,masterDir,gitUrl):
        myloger(name=serverName, msg="初始化本地仓库:%s" % masterDir)
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

        myloger(serverName, msg="本地git仓库当前项目认证")
        config_cmd = "git config --local credential.helper store"
        config_cmd2 ="git config --global push.default simple"
        config_cmd3 ="git config --global http.postBuffer 242880000"
        execSh(serverName,config_cmd)
        execSh(serverName,config_cmd2)
        execSh(serverName,config_cmd3)

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

    def checkBranch(self, masterBranch):
        # 获取项目分支是否为master
        myloger(name=self.serverName, msg="检查当前分支：%s " % masterBranch)
        os.chdir(self.masterDir)
        cmd = "git branch"
        stdout, stderr = execSh(self.serverName,cmd)
        branch_list = [i.strip() for i in stdout.split("\n") if i]
        print(branch_list)
        branchName_str = "* %s" % masterBranch
        if branchName_str in branch_list[0]:
            myloger(name=self.serverName, msg="当前分支：%s " % masterBranch)
            return True
        return False

    def branchExist(self,masterBranch):
        # 获取项目分支是否为master
        cmd = "git branch"
        stdout, stderr = execSh(self.serverName,cmd)
        branch_list = [i.strip() for i in stdout.split("\n")]
        branchName_str = "%s" % masterBranch
        if branchName_str in branch_list:
            myloger(name=self.serverName, msg="%s 分支已经存在" % masterBranch)
            return True
        return False

    def readStdin(self):
        input_str = raw_input("确认执行操作：Y/N")
        return input_str.strip().lower()

    def merge(self, branchName,masterBranch):
        myloger(name=self.serverName, msg="合并分支：%s 至 %s" % (branchName, masterBranch))
        try:
            myloger(name=self.serverName, msg="切换工作目录")
            os.chdir(self.masterDir)  # 切换工做目录
        except Exception as e:
            print(e)
            return False
        execSh(self.serverName,"git pull")
        execSh(self.serverName,"git checkout %s" % branchName)
        myloger(name=self.serverName, msg="取分支:%s" % branchName)
        fetch_cmd = "git fetch origin %s" % branchName
        stdout, stderr = execSh(self.serverName, fetch_cmd)
        if "fatal" in stderr or "error" in stderr:
            self. myloger(name=self.serverName, msg="stderr:%s" % stderr)
            myloger(name=self.serverName, msg="请检查分支 branchname:%s" % branchName)
            return False
        myloger(name=self.serverName, msg="更新本地分支")
        pull_cmd = "git pull"
        execSh(self.serverName, pull_cmd)
        # 切换至master分支
        myloger(name=self.serverName, msg="切换至%s分支 " % masterBranch)
        checkout_m_cmd = "git checkout %s" % masterBranch
        stdout,stderr = execSh(self.serverName,checkout_m_cmd)
        if "pathspec '%s' did not match" % masterBranch in stderr:
            myloger(name=self.serverName, msg="分支：%s 不存在 " % masterBranch)
            return False
        myloger(name=self.serverName, msg="更新%s分支" % masterBranch)
        execSh(self.serverName,pull_cmd)
        myloger(name=self.serverName, msg="是否合并分支：%s 至%s" % (branchName, masterBranch))
        merge_cmd = "git merge %s" % branchName
        stdout, stderr = execSh(self.serverName,merge_cmd)
        if "Merge conflict" in stderr:
            myloger(name=self.serverName, msg="合并分支：%s 至 %s,存在冲突！" % (branchName, masterBranch))
            return False
        # 提交合并的master 至源端git库
        # 需要加确认 文件修改，在判断是否推送源端
        # myloger(name=self.serverName, msg="是否提交合并的%s至远端git库" % masterBranch)
        # option = self.readStdin()
        # if option != "y":
        #     myloger(name=self.serverName, msg="取消分支合并：%s" % self.serverName)
        #     return False
        push_cmd = "git push"
        execSh(self.serverName,push_cmd)
        return True

    def reinit(self, serverName,masterDir,gitUrl):
        self.serverName= serverName
        self.masterDir = masterDir
        myloger(name=self.serverName, msg="重新初始化：%s" % self.serverName)
        if os.path.exists(self.masterDir):
            myloger(name=self.serverName, msg="删除原仓库目录：%s" % self.masterDir)
            shutil.rmtree(self.masterDir)
        self.init(self.serverName, self.masterDir, gitUrl)
        return True

    def pull(self, masterBranch):
        myloger(name=self.serverName, msg="更新分支:%s," % masterBranch)
        myloger(name=self.serverName, msg="切换工作目录:%s," % self.masterDir)
        os.chdir(self.masterDir)
        myloger(name=self.serverName, msg="拉取远端分支")
        execSh(self.serverName,"git fetch")
        myloger(name=self.serverName, msg="切换分支:%s" % masterBranch)
        checkout_b_cmd = "git checkout %s" % masterBranch
        stdout, stderr = execSh(self.serverName,checkout_b_cmd)
        if "did not match any file(s) known to git" in stderr:
            myloger(name=self.serverName, msg="分支:%s 错误，请检查！" % masterBranch)
            return False
        myloger(name=self.serverName, msg="更新分支:%s," % masterBranch)
        pull_cmd = "git pull"
        execSh(self.serverName,pull_cmd)
        return True

    def push(self,branchName):
        try:
            myloger(name=self.serverName, msg="切换工作目录")
            os.chdir(self.masterDir)  # 切换工做目录
        except Exception as e:
            print(e)
            return False
        myloger(name=self.serverName, msg="更新%s分支" % branchName)
        execSh(self.serverName, "git add .")
        execSh(self.serverName, "git commit -m 'cmdpush'")
        execSh(self.serverName, "git push")
        return True


    def createBranch(self,masterBranch,branchName):
        myloger(name=self.serverName, msg="从分支:%s 新建分支%s,并且切换" % (masterBranch,branchName))
        checkout_b_cmd = "git checkout -b %s" % branchName
        push_cmd = "git push origin %s -u" % branchName
        os.chdir(self.masterDir)
        execSh(self.serverName,"git checkout %s" % masterBranch)
        myloger(name=self.serverName, msg="新建分支%s,并且切换" % branchName)
        stdout, stderr = execSh(self.serverName,checkout_b_cmd)
        if "fatal: A branch named '%s' already exists" % branchName in stderr:
            myloger(name=self.serverName, msg="分支%s,已经存在！" % branchName)
            return False
        myloger(name=self.serverName, msg="关联远程分支%s,并提交" % branchName)
        stdout, stderr = execSh(self.serverName,push_cmd)
        return True

    def deleteBranch(self,masterBranch,branchName):
        if branchName == "master":
            myloger(name=self.serverName, msg="删除分支:%s 不允许！！" % branchName)
            return False
        os.chdir(self.masterDir)
        myloger(name=self.serverName, msg="删除分支:%s" % branchName)
        execSh(self.serverName,"git checkout %s" % masterBranch)
        myloger(name=self.serverName, msg="删除本地分支%s！" % branchName)
        stdout, stderr = execSh(self.serverName,"git branch -d %s" % branchName)
        if "branch '%s' not found" % branchName in stderr:
            myloger(name=self.serverName, msg="分支%s,不存在！" % branchName)
            return True
        myloger(name=self.serverName, msg="删除远端分支%s！" % branchName)
        execSh(self.serverName,"git push origin --delete %s" % branchName)
        return True

    def revert(self, masterBranch,commitId):
        commitDict = self.getCommitList(masterBranch)
        date_now = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
        if not self.pull(masterBranch):
            return False
        config_cmd = 'git config --global user.email "jenkins@example.com"'
        config_cmd2 = 'git config --global user.name "jenkins"'
        execSh(self.serverName,config_cmd)
        execSh(self.serverName,config_cmd2)
        if commitId and commitId in commitDict:
            myloger(name=self.serverName, msg="分支%s,版本回退指定版本:%s,且提交远程" % (masterBranch,commitId))
            execSh(self.serverName,"git revert HEAD -n %s" % commitId)  # 回退到上一个版本
            execSh(self.serverName,"git commit -m 'rollback commit:%s'" % commitId)
        # elif not commitDict.has_key(commitId):
        #     myloger(name=self.serverName, msg="分支%s,版本回退指定版本:%s,错误" % (masterBranch, commitId))
        #     return False
        else:
            myloger(name=self.serverName, msg="分支%s,版本回退上一个版本,且提交远程" % masterBranch)
            execSh(self.serverName,"git revert HEAD -n")  # 回退到上一个版本
        execSh(self.serverName,"git push")

    def getCommitList(self, masterBranch):
        os.chdir(self.masterDir)
        if not masterBranch:
            myloger(name=self.serverName, msg="获取分支%s,历史版本commitid 错误" % (masterBranch))
            return False
        myloger(name=self.serverName, msg="获取分支%s,历史版本commitid" % (masterBranch))
        execSh(self.serverName,"git checkout %s" % masterBranch)
        execSh(self.serverName,"git pull")  # 回退到上一个版本
        stdout,stderr = execSh(self.serverName,"git log -10")  # 获取最新10个版本
        commitList = stdout.split("commit")
        commitDict = {}
        for i in commitList:
            if i.strip():
                sublist = [j.strip() for j in i.strip().split("\n") if j]
                commitDict[sublist[0]] = sublist[1:]
        return commitDict


if __name__ == "__main__":
    ConfPATH = "/python_yek/xkj-k8s/xkj/xkj-config.yaml"
    g = git(ConfPATH, "express-admin")
    # g.reinit()
    print(g.serverName)
