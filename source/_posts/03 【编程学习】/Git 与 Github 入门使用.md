---
title: Git 入门笔记
tags: 
- git
- github 
categories:
- 速查手册
---

命令：`git commit` `git pull` `git push`

<!-- more -->

## 一 如何将本地的新项目提交到GitHub

[如何通过git 提交代码到远程仓库？](https://zhuanlan.zhihu.com/p/152332683)

### 1.初始化本地仓库

```bash
git init
```

### 2.将所有文件添加到本地仓库（也可添加你所需的文件）

```bash
git add .
```

### 3.将项目提交到本地git仓库 （“first commit” 是备注信息）

```bash
git commit -m "first commit"
```



### 4.本地git仓库与远程仓库关联（两种方式：1.https方式；2.SSL方式）

```bash
git remote add origin https://github.com/JianhaoChung/DGL_GCNER.git
```

或

```bash
git remote add origin  git@github.com:JianhaoChung/DGL_GCNER.git
```

### 5.将项目推送到远程仓库

```bash
git push -u origin master
```



## 二 Git更新本地项目上传到github

### 1、添加到本地仓库

```
git add .
```

### 2 添加提交描述

```
git commit -m ‘second commit’
```

### 3 提交前先从远程仓库主分支中拉取请求

```
git pull origin master
```

### 4 把本地仓库代码提交

```
git push -u origin master
```

> 引用

[视频同步笔记：狂神聊Git (qq.com)](https://mp.weixin.qq.com/s/Bf7uVhGiu47uOELjmC5uXQ)

[git 小游戏](https://learngitbranching.js.org/?locale=zh_CN)

## 三 GitHub 免密Push

<img src="https://raw.githubusercontent.com/conf-haolee/Images/master/uPic/ed055bb1c6ac809a98e8fd8051facb40_720.png" alt="ed055bb1c6ac809a98e8fd8051facb40_720" style="zoom:80%;" />
