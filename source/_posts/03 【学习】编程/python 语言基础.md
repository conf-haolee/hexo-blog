---
title: python 语言基础
date: 2021-10-15
tags: 
- python
- json 
categories:
- 编程学习
---

Python 是一门优雅而健壮的编程语言，它继承了传统编译语言的强大性和通用性，同时也借鉴了脚本语言和解释语言的易用性。

<!--more-->

第一步：搭建编程环境， 建议直接安装Anaconda。

## 01 Python语言介绍

Python 是一个高层次的结合了解释性、编译性、互动性和面向对象的脚本语言。
```c++
int* func()
{
	int* a = new int(10);
	return a;
}

int main() {

	int *p = func();

	cout << *p << endl;
	cout << *p << endl;
    
	system("pause");

	return 0;
}
```

## 02 变量与简单数据类型

### 2.1 变量

变量的命名规范与使用

- 变量名只能包含字母、数字和下划线。变量名可以字母或下划线打头，但不能以数字打头，例如，可将变量命名为message_1，但不能将其命名为1_message。
- 变量名不能包含空格，但可使用下划线来分隔其中的单词。例如，变量名greeting_message 可行，但变量名greeting message会引发错误。 
- 不要将Python关键字和函数名用作变量名，即不要使用Python保留用于特殊用途的单词， 如print（请参见附录A.4）。  
- 变量名应既简短又具有描述性。例如，name比n好，student_name比s_n好，name_length 比length_of_persons_name好。 

<u>慎用小写字母l和大写字母O，因为它们可能被人错看成数字1和0。</u>  

要创建良好的变量名，需要经过一定的实践，在程序复杂而有趣时尤其如此。随着你编写的程序越来越多，并开始阅读别人编写的代码，将越来越善于创建有意义的变量名。

### 2.2 字符串

字符串就是一系列字符。在Python中，**用引号括起的都是字符串，其中的引号可以是单引号， 也可以是双引号，**如下所示.

```
"This is a string." 
'This is also a string.'
```

#### 使用方法修改字符串的大小写 

对于字符串，可执行的最简单的操作之一是修改其中的单词的大小写。

```
name = "ada lovelace"  
print(name.title())   # 输出：Ada Lovelace
```

在name.title()中，name后 面的句点（.）让Python对变量name执行方法title()指定的操作。

```
name = "Ada Lovelace" 
print(name.upper())   # 输出 ADA LOVELACE 
print(name.lower())   # 输出 ada lovelace
```

> 存储数据时，方法lower()很有用。很多时候，你无法依靠用户来提供正确的大小写，因此 需要将字符串先转换为小写，再存储它们。以后需要显示这些信息时，再将其转换为最合适的大 小写方式。 

#### 合并（拼接）字符串

Python使用加号（+）来合并字符串。

#### 使用制表符或换行符来添加空白

在编程中，空白泛指任何非打印字符，如空格、制表符和换行符。你可使用空白来组织输出， 以使其更易读。 

#### 删除空白

Python能够找出字符串开头和末尾多余的空白。要确保字符串末尾没有空白，可使用方法 rstrip()。 

为删除这个字符串中的空白，你需要将其末尾的空白剔除，再将结果存回到原来的变量中。

```
favorite_language = 'python ' 
favorite_language = favorite_language.rstrip() 
favorite_language   # 输出'python'
```

此外，你还可以剔除字符串开头的空白，或同时剔除字符串两端的空白。为此，可分别使用方法 lstrip()和strip()：

### 2.3 数字

#### 整数

#### 浮点数

Python将带小数点的数字都称为浮点数。大多数编程语言都使用了这个术语，它指出了这样 一个事实：小数点可出现在数字的任何位置。每种编程语言都须细心设计，以妥善地处理浮点数， 确保不管小数点出现在什么位置，数字的行为都是正常的。

#### 使用函数str()避免类型错误

函数str()数字转字符串。

## 03 列表类型的介绍与操作

列表由一系列按特定顺序排列的元素组成。

在Python中，用方括号（[]）来表示列表，并用逗号来分隔其中的元素。

下面是一个简单的 列表示例，这个列表包含几种自行车：  

```
bicycles = ['trek', 'cannondale', 'redline', 'specialized']  
print(bicycles)
```

#### 访问列表元素

列表是有序集合，因此要访问列表的任何元素，只需将该元素的位置或索引告诉Python即可。

在Python中，第一个列表元素的索引为0，而不是1。在大多数编程语言中都是如此，这与列表操作的底层实现相关。

Python为访问最后一个列表元素提供了一种特殊语法。**通过将索引指定为-1，可让Python返 回最后一个列表元素**

#### 修改列表元素

```
motorcycles = ['honda', 'yamaha', 'suzuki'] 
print(motorcycles) 
motorcycles[0] = 'ducati' 
```

#### 在列表中添加元素

```
motorcycles.append('ducati')   # 列表末尾添加元素
```

在列表中插入元素 

```
motorcycles.insert(0, 'ducati')  #使用方法insert()可在列表的任何位置添加新元素。
```

#### 从列表中删除元素

1. 使用del语句删除元素    `del motorcycles[0]`

2. 使用方法pop()删除元素

   1. 有时候，你要将元素从列表中删除，并接着使用它的值。 

      ```
       popped_motorcycle = motorcycles.pop()
      ```

3. 弹出列表中任何位置处的元素  `first_owned = motorcycles.pop(0)`

4. 根据值删除元素    `motorcycles.remove('ducati')`

> 方法remove()只删除第一个指定的值。如果要删除的值可能在列表中出现多次，就需要使用循环来判断是否删除了所有这样的值。

#### 组织列表



## 04 字典类型的介绍与操作

> 在Python中，字典是一系列键—值对。每个键都与一个值相关联，你可以使用键来访问与之 相关联的值。与键相关联的值可以是数字、字符串、列表乃至字典。事实上，可将任何Python对 象用作字典中的值。 



## 05 流程控制

在Python中检查是否相等时区分大小写，例如，两个大小写不同的值会被视为不相等：

1. 使用`and`检查多个条件 
2.  使用`or`检查多个条件
3. 要判断特定的值是否已包含在列表中，可使用关键字`in`。
4. 检查特定值是否不包含在列表中,可使用关键字`not in`。

经常需要检查超过两个的情形，为此可使用Python提供的if-elif-else结构。

## 06 用户输入与循环

使用函数input()时，Python将用户输入解读为字符串。请看下面让用户输入其年龄的解释器 会话：  >>> 

```python
>>> age = input("How old are you? ")  
How old are you? 21 
>>> age  
'21'  
```

使用int()来获取数值输入 , **int() 强制类型转换为整型**

## 07 函数

```python
def greet_user(): 
     """显示简单的问候语""" 
     print("Hello!") 
greet_user() 
```

编写函数时，可给每个形参指定默认值。

如果要描述的动物不是小狗，可使用类似于下面的函数调用：  

```
def describe_pet(pet_name, animal_type='dog'): 
    """显示宠物的信息""" 
    print("\nI have a " + animal_type + ".") 
    print("My " + animal_type + "'s name is " + pet_name.title() + ".") 
describe_pet(pet_name='willie')

describe_pet(pet_name='harry', animal_type='hamster')  
```

由于显式地给animal_type提供了实参，因此Python将忽略这个形参的默认值。

> 使用默认值时，在形参列表中必须先列出没有默认值的形参，再列出有默认值的实参。 这让Python依然能够正确地解读位置实参。 

#### 将实参变成可选的

有时候，需要让实参变成可选的，这样使用函数的人就只需在必要时才提供额外的信息。可使用默认值来让实参变成可选的。  例如，假设我们要扩展函数get_formatted_name()，使其还处理中间名。为此，可将其修改 成类似于下面这样：

```python
def get_formatted_name(first_name, last_name, middle_name=''): 
"""返回整洁的姓名""" 
	if middle_name: 
         full_name = first_name + ' ' + middle_name + ' ' + last_name 
	else: 
		full_name = first_name + ' ' + last_name
```

Python将非空字符串解读为True.

#### 函数返回值

函数可返回任何类型的值，包括列表和字典等较复杂的数据结构。

函数传递列表

- 在函数中修改列表
- 禁止函数修改列表

有时候，可向函数传 递列表的副本而不是原件；这样函数所做的任何修改都只影响副本，而丝毫不影响原件。  要将列表的副本传递给函数，可以像下面这样做：  

```python
function_name(list_name[:])  
```

切片表示法[:]创建列表的副本。

虽然向函数传递列表的副本可保留原始列表的内容，但除非有充分的理由需要传递副本，否 则还是应该将原始列表传递给函数，因为让函数使用现成列表可避免花时间和内存创建副本，从 而提高效率，在处理大型列表时尤其如此。 

#### 传递任意数量的实参

有时候，你预先不知道函数需要接受多少个实参，好在Python允许函数从调用语句中收集任 意数量的实参。  例如，来看一个制作比萨的函数，它需要接受很多配料，但你无法预先确定顾客要多少种配 料。下面的函数只有一个形参***toppings**，但不管调用语句提供了多少实参，这个形参都将它们 统统收入囊中： 

```python
def make_pizza(*toppings): 
	"""打印顾客点的所有配料""" 
	print(toppings) 
make_pizza('pepperoni') 
make_pizza('mushrooms', 'green peppers', 'extra cheese')
```

#### 结合使用位置实参和任意数量实参

如果要让函数接受不同类型的实参，必须在函数定义中将接纳任意数量实参的形参放在最 后。

#### 使用任意数量的关键字实参

有时候，需要接受任意数量的实参，但预先不知道传递给函数的会是什么样的信息。在这种 情况下，可将函数编写成能够接受任意数量的键—值对——调用语句提供了多少就接受多少。一 个这样的示例是创建用户简介：你知道你将收到有关用户的信息，但不确定会是什么样的信息。 在下面的示例中，函数build_profile()接受名和姓，同时还接受任意数量的关键字实参： 

```python
def build_profile(first, last, **user_info): 
    """创建一个字典，其中包含我们知道的有关用户的一切""" 
    profile = {} 
	profile['first_name'] = first 
    profile['last_name'] = last 
    ....
```

#### 将函数存储在模块中

import语句允许在当前运行的程序文件中使用模块中的代码。 

#### 导入特定的函数

```python
from module_name import function_name
```

#### 使用as给函数指定别名

## 08 类

**面向对象编程**是最有效的软件编写方法之一。

使用类几乎可以模拟任何东西。下面来编写一个表示小狗的简单类Dog——它表示的不是特 定的小狗，而是任何小狗。

根据约定，在Python中，<u>首字母大写</u>的名称指的是类。

方法\_\_init\_\_()  类中的函数称为方法；你前面学到的有关函数的一切都适用于方法，就目前而言，唯一重要 的差别是调用方法的方式。

在这个方法的名称中，开头和末尾各有两个下划线，这是一种约 定，旨在避免Python默认方法与普通方法发生名称冲突。



## 09 文件与异常

### 9.1 读取文件

```python
with open('pi_digits.txt') as file_object: 
    contents = file_object.read() 
    print(contents) 
```

相比于原始文件，该输出唯一不同的地方是末尾多了一个空行。为何会多出这个空行呢？因为read()到达文件末尾时返回一个空字符串，而将这个空字符串显示出来时就是一个空行。要删除多出来的空行，可在print语句中使用rstrip()：

```
with open('pi_digits.txt') as file_object: 
    contents = file_object.read() 
    print(contents.rstrip()) 
```

### 9.2 文件路径

绝对路径 or 相对路径

Linux系统下路径

```python
file_path = '/home/ehmatthes/other_files/text_files/filename.txt' 
with open(file_path) as file_object: 
```

Window系统下路径

```python
file_path = 'C:\Users\ehmatthes\other_files\text_files\filename.txt' 
with open(file_path) as file_object: 
```

**注意：**Windows系统有时能够正确地解读文件路径中的斜杠。如果你使用的是Windows系统，且 结果不符合预期，请确保在文件路径中使用的是反斜杠。

**注意：**读取文本文件时，Python将其中的所有文本都解读为字符串。如果你读取的是数字，并 要将其作为数值使用，就必须使用函数int()将其转换为整数，或使用函数float()将其转 换为浮点数。

圆周率值中包含你的生日吗？ 练习[圆周率中包含你的生日吗_-CSDN博客](https://blog.csdn.net/weixin_51149598/article/details/120632533)

### 9.3 写入文件

```python
filename = 'programming.txt' 
 
with open(filename, 'w') as file_object: 
    file_object.write("I love programming.\n") 
    file_object.write("I love creating new games.\n")
```

如果你要给文件添加内容，而不是覆盖原有的内容，可以附加模式打开文件。

```python
filename = 'programming.txt' 
 
with open(filename, 'a') as file_object: 
    file_object.write("I also love finding meaning in large datasets.\n") 
    file_object.write("I love creating apps that can run in a browser.\n")
```

最终的结果是，文件原来的内容还在，它们后面是我们刚添加的内容。

### 9.4 异常

Python使用被称为异常的特殊对象来管理程序执行期间发生的错误。

异常是使用try-except代码块处理的。try-except代码块让Python执行指定的操作，同时告 诉Python发生异常时怎么办。

处理ZeroDivisionError异常：

```python
try: 
    print(5/0) 
except ZeroDivisionError: 
    print("You can't divide by zero!")
```

### 9.5 存储数据

用户关闭程序时，你几乎总是要保存他们提供的信息；一种简单的方式是使用模块json来存储数据。 

> JSON（JavaScript Object Notation）格式最初是为JavaScript开发的，但随后成了一种常见 格式，被包括Python在内的众多语言采用。

#### 使用json.dump()和 json.load()

对于用户生成的数据，使用json保存它们大有裨益，因为如果不以某种方式进行存储，等程 序停止运行时用户的信息将丢失。。下面来看一个这样的例子：用户首次运行程序时被提示输入自己的名字，这样再次运行程序时就记住他了。

```python
filename = 'username.json' 
try: 
    with open(filename) as f_obj: 
        username = json.load(f_obj) 
except FileNotFoundError: 
    username = input("What is your name? ") 
    with open(filename, 'w') as f_obj: 
        json.dump(username, f_obj) 
        print("We'll remember you when you come back, " + username + "!") 
else: 
    print("Welcome back, " + username + "!")
```

#### 重构

你经常会遇到这样的情况：代码能够正确地运行，但可做进一步的改进——将代码划分为 一系列完成具体工作的函数。这样的过程被称为重构。重构让代码更清晰、更易于理解、更容易扩展。

- [ ] todo

## 10 测试代码

- [ ] toto


## 11 实战项目集合

> 使用help() 和dir() 查看python 源码

Python自带的**help()函数**可以为我们提供函数的文档字符串以及函数的一些基本信息。

**dir()函数**可以列出对象的所有属性和方法，包括内置函数。

> 参考

[Python编程 从入门到实战](https://pan.baidu.com/s/1z1j6vc_L_xS4WwoIWv8B-g?pwd=lhao)

[利用Python 进行数据分析](https://pan.baidu.com/s/1DbPCc-c-G0YiLmD_Y_HEFw?pwd=lhao)

[Python之路V2.0.pdf](https://pan.baidu.com/s/1wcyEBhVmPQdh_iXZ87xp_A?pwd=lhao)

免费电子书，分析文本用[Free eBooks | Project Gutenberg](https://gutenberg.org/)