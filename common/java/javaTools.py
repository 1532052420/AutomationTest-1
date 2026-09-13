#-*- coding:utf8 -*-
# 创建时间 2018/01/19 22:36
import os
import platform
import jpype

class JavaTool:

    # slf4j-log4j12(绑定) 与 libs 中已有的 log4j-over-slf4j(桥接) 并存会触发
    # slf4j 绑定死循环检测，JVM 内 Tess4j 初始化直接失败，构建 classpath 时必须排除
    EXCLUDED_JARS = ('slf4j-log4j12',)

    @classmethod
    def getAllJar(cls):
        split_flag=':'
        if 'Windows'==platform.system():
            split_flag=';'
        result=''
        libpath=os.path.join(os.path.abspath('common/java/lib/'),'')
        path=os.walk(libpath)
        for dirpath,dirname,filenames in path:
            for filename in filenames:
                if filename.endswith('.jar') and not any(x in filename for x in cls.EXCLUDED_JARS):
                    filepath=os.path.join(dirpath,filename)
                    result=result+split_flag+filepath
        return result.lstrip(split_flag)

class StartJpypeJVM(object):
    """
    采用单例模式，保证一个进程里只启动一个jvm
    """
    __instance = None
    __inited = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance=object.__new__(cls)
        return cls.__instance

    def __init__(self):
        if self.__inited is None:
            jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", "-Djava.class.path=" + JavaTool.getAllJar(),convertStrings=False)
            self.__inited = True