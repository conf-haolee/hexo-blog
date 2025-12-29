---
title: Halcon 基础知识
date: 2024-10-15
tags: 
- Volantis
- hexo 
categories:
- 速查手册
---

HALCON是德国MVtec公司开发的一套完善的标准的机器**视觉算法包**，它节约了产品成本，缩短了软件开发周期。

<!--more-->

快速学习做法：研究实例、做实战项目。halcon不能提供相应的界面编程需求，需要和vs来构造MFC界面或者QT使用，才能构成一套完整软件。

HDevelop 开发环境的安装：

[HALCON20.11软件 64 破解](https://pan.baidu.com/s/1zaRWtuyo_QDQS_2LU_ko1Q?pwd=lhao)

## HDevelop语言特点介绍

halcon 中有两种变量，对应两种参数类型： 图形对象（图像，区域和XLD） 和控制数据（数字，字符串）。

图像： 显示图向类型和尺寸的通道数量。 如果过图形变量包含多个图像，那么显示第一个图像的属性。

region: 显示区域的而面积和中心。

XLD:  显示轮廓点的数量和长度。



在HDevelop参数列表中四种参数总是以同样的顺序出现，如下：

`算子名（图形输入： 图形输出： 控制输入： 控制输出）`

变量的定义与赋值

```
index := 10
```

## Halcon常用算子介绍

### 显示相关

```
打开一个窗口
dev_open_window()

打开一个适应图像大小的窗口
dev_open_window_fit_image

获取图像窗口句柄
dev_get_window ()

清除图像窗口的内容
dev_clear_window ()

关闭活动窗口
dev_close_window()
显示图像
dev_display()

在当前窗口显示文字
dev_disp_text()

在指定窗口显示文字
disp_message(）

设置显示字体类型
set_display_font()

设置显示颜色
dev_set_color()

设置轮廓线的线宽
dev_set_line_width()

定义区域填充模式
dev_set_draw()
```

### 图像相关

```
加载图像
read_image()

保存图像
write_image()

剪切一个或多个矩形图像区域
crop_part()

彩色图转灰度图
rgb1_to_gray()

灰度转彩色
compose3()

灰度值取反
invert_image()

三通道彩色图像分离
decompose3()

获取图像的Roi
reduce_domain()

获取图像尺寸
get_image_size()

确定区域内的最小和最大灰度值。
min_max_gray()

计算灰度值的平均值和偏差。
intensity()

两张图像相加
add_image()

两张图像相减
sub_image()

计算两幅图像的最大值
max_image()

计算两幅图像的最小值
min_image()

镜像图像
mirror_image()

围绕图像中心旋转图像
rotate_image()

将图像缩放到给定的大小
zoom_image_size()

以固定灰度值将区域绘制到图像中
paint_region()

计算灰度值直方图
gray_histo()
直方图转换为区域
gen_region_histo()

根据灰度值特征选择区域
select_gray()
```

## 案例参考

阈值分割识别车牌，HDevelop示例程序threshold.hdev.

```
read_image (Audi2, 'audi2')
fill_interlace (Audi2, ImageFilled, 'odd')
threshold (ImageFilled, Region, 0, 90)
connection (Region, ConnectedRegions)
select_shape (ConnectedRegions, SelectedRegions, 'width', 'and', 30, 70)
select_shape (SelectedRegions, Letters, 'height', 'and', 60, 110)
dev_clear_window ()
dev_set_colored (12)
dev_display (ImageFilled)
dev_display (Letters)
```

> 参考

halcon 工业应用实用教程 第一册——第四册

[机器视觉(Halcon) 河南理工大学 苏波](https://www.bilibili.com/video/BV1PU4y177AT/?p=8&share_source=copy_web&vd_source=2b642316ba0d5f71a2bf75410183788c)