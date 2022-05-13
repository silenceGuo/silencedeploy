#!/usr/bin/deploytEnv python
# -*- coding: utf-8 -*- 
# @Time : 2022-4-14 上午 9:00 
# @Author : damon.guo 
# @File : main.py 
# @Software: PyCharm

def main():
    print("k8s env")
    print("执行 python \silencedeploy\control\k8s\deploy_controlk8s.py -n name -e env -a status -m master -p projectName -v v1")
    print("#"*50)
    print("normal env")
    # 执行 python \silencedeploy\control\k8s\deploy_controlk8s.py -n name -e env -a status -m master -p projectName -v v1
    print("执行 python \silencedeploy\control\\normal\deploy_control.py -n name -e env -a status -m master -p projectName -v v1")
    print("#" * 50)

main()