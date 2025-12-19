---
title: Qt 实现多线程
tags: 
- Qt
- 多线程 
categories:
- 编程学习
---

1，继承Qthread ,重写run方法。

<!-- more -->

## 发展史

- **version-4.6以前**，**只能继承QThread**来实现
- **version-4.6以后**，官方推荐使用**继承QObject** 来实现



## Qthread 存在的问题：





## 方法一：继承Qthread



Step1. **需要创建一个线程类的子类**，让其继承QT中的线程类QThread，比如：

```C++
class MyThread:public QThread
{
    ......
}
```

step2. **重写父类中run() 方法**，在该函数内部编写子线程要处理的具体的业务流程

```
class MyThread:public QThread
{
    ......
 protected:
    void run()
    {
        ........
    }
}
```

step3. **在主线程中创建子线程对象，new 一个**就可以了

```
MyThread * subThread = new MyThread;
```

Step4. **启动子线程，调用 start () 方法**

```
subThread->start();
```



### 开始实验：

1. #### 用方法一继承Qthread的方式开辟子线程读取excel 

   分别试验三个不同的读写excel文件

   第一次

   ------

   :one:**创建线程子类**

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230425150141112.png" alt="image-20230425150141112" style="zoom:50%;" />

:two:**重写父类中run()方法**

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230425150018070.png" alt="image-20230425150018070" style="zoom:50%;" />

:three:**主线程中创建子类**

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230425150332648.png" alt="image-20230425150332648" style="zoom:50%;" />

:four:**启动子线程**

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230425150609443.png" alt="image-20230425150609443" style="zoom:50%;" />

> 结果： 成功创建子线程，excel 读写函数chart() 被调用，但未见保存成功的文件

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230425150922036.png" alt="image-20230425150922036" style="zoom:50%;" />

------

第二次

...

## 方法二：**继承QObject** 

Qt 提供了第二种线程的创建方式弥补了第一种方式的缺点，用起来更加灵活，但是这种方式写起来会相对复杂u一些，其操作步骤如下：

**step1 创建一个新类，让这个类从QObject派生**



**step2** 在这个类中**添加一个公共的成员函数**，函数体就是我们要子线程中执行的业务逻辑

```
class MyWork:public QObject
{
public:
    .......
    // 函数名自己指定, 叫什么都可以, 参数可以根据实际需求添加
    void working();
}
```

**step3** 在**主线程中创建一个 QThread 对象**，这就是子线程的对象

```
QThread* sub = new QThread;
```

**step4** **在主线程中创建工作的类对象**（千万不要指定给创建的对象指定父对象）

```
MyWork* work = new MyWork(this);    // error
MyWork* work = new MyWork;          // ok
```

**Step5** 将 MyWork 对象移动到创建的子线程对象中，需要调用 QObject 类提供的 moveToThread() 方法

```
// void QObject::moveToThread(QThread *targetThread);
// 如果给work指定了父对象, 这个函数调用就失败了
// 提示： QObject::moveToThread: Cannot move objects with a parent
work->moveToThread(sub);	// 移动到子线程中工作
```



**step6** **启动子线程，调用 start()**, 这时候线程启动了，但是移动到线程中的对象并没有工作

**Step7** **调用 MyWork 类对象的工作函数**，让这个函数开始执行，这时候是在移动到的那个子线程中运行的



### 开始实验：

第一次 excel chart()函数

过程 略

> 结果 同方法一的结果  保存文件失败

<img src="https://raw.githubusercontent.com/silent426/Images/master/uPic/image-20230425160545238.png" alt="image-20230425160545238" style="zoom:50%;" />

## 总结：





参考：

[Qt 中多线程的使用 | 爱编程的大丙 (subingwen.cn)](https://subingwen.cn/qt/thread/)