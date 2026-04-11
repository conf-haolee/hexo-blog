---
title: 利用blender python自动渲染密封圈下落场景图片【bpy生成仿真图片数据集】
date: 2024-11-20
pin: false
tags: 
- blender
- python
- bpy
categories:
- 学习
---

<div align="center"><img src=https://raw.githubusercontent.com/conf-haolee/Images/master/PicGoImg/202411201721298.png width=300px /></div>

<!-- more-->

## auto_render_with_bpy

使用blender-python 自动渲染模拟出的密封圈下落场景图片

完整仓库地址：[conf-haolee/auto-render-with-bpy](https://github.com/conf-haolee/auto-render-with-bpy/tree/main)

实例图片

- 密集下落场景模拟文件：**fallRingsCircleSimulation.blend**

<div align="center"><img src=https://raw.githubusercontent.com/conf-haolee/Images/master/PicGoImg/202411201637695.png width=600px /></div>

- 自动渲染程序：**auto_render_torus_simulate_fall.py**


<div align="center"><img src=https://raw.githubusercontent.com/conf-haolee/Images/master/PicGoImg/202411201713357.png width=600px /></div>

- 渲染指定数量`labeled bmp`密封圈图片程序：**auto_render_torus_with_overlap.py**

<div align="center"><img src=https://raw.githubusercontent.com/conf-haolee/Images/master/PicGoImg/202411201721298.png width=600px /></div>


> 环境配置

`Python 3.11.9`
`blender 4.1`
`bpy-4.1.0-cp311-cp311-win_amd64.whl`
官方软件下载
https://download.blender.org/release/Blender4.1/
bpy模块离线下载
https://pypi.tuna.tsinghua.edu.cn/simple/bpy/