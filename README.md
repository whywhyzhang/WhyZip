## 介绍 | Introduction

本项目包括Python写的Zip工具

1. 生成一个无线循环的Zip文件，或者称为Zip奎因
   输入：一个文件，文件大小需要限制在30KB以内。
   输出：一个Zip压缩包，解压该压缩包会生成两个文件：上面输入的文件，以及相同的Zip压缩包。

This project contains zip tools writed by Python.

1. Generate an infinite loop zip file, aka Zip Quine
   Input: a file wanted to be included in this zip file, the file's size should less than 30KB
   Output: a zip file, decompress it will get 2 files: the input file, and the same zip file. 

## 使用方法 | Usage

1. Generate Zip Quine:
   ```
   python3 ./src/QuineGenerator.py out.zip test.txt
   ```

## 引用 | Attribution

如下文章或项目在本项目中被引用，并基于文章的思路进行修改 | The following articles or projects was referenced and modified in this project

- **Zip Files All The Way Down** by **Russ Cox**, [URL](https://research.swtch.com/zip), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Modifications were made to the original content. And thanks for the sharing.
- **The SNIPPETS Portable C/C++ Source Code Collection** by **Bob Stout**, [URL](https://web.archive.org/web/20080303102530/http://c.snippets.org/snip_lister.php?fname=crc_32.c).

## 许可 | License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details.
