# -*- coding: utf-8 -*-
"""代码调试 · common/ 通用工具类检查项"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dbg_kit import check, Skip, assert_true, tmp_workdir, setup_java_home

@check('common.dateTimeTool', 'common/dateTimeTool.py', '日期时间工具：时间戳/字符串互转、日期运算')
def _():
    from common.dateTimeTool import DateTimeTool
    now = DateTimeTool.getNowTime()
    assert_true(len(now) == 19, 'getNowTime 格式异常: %r' % now)
    ts = DateTimeTool.getNowTimeStampWithSecond()
    dt = DateTimeTool.timeStampToDateTime(ts)
    assert_true(dt.strftime('%Y-%m-%d') == DateTimeTool.getNowDate(), '时间戳转日期不一致')
    ts2 = DateTimeTool.strToTimeStamp(DateTimeTool.getNowTime())
    assert_true(abs(int(ts2) - int(ts)) <= 2, '当前时间字符串转时间戳偏差过大: %s vs %s' % (ts, ts2))
    ms = str(DateTimeTool.getNowTimeStampWithMillisecond())
    assert_true(len(ms) == 13, '毫秒时间戳应为13位: %r' % ms)
    yesterday = DateTimeTool.getHowDaysAgo(DateTimeTool.getNowTime(), howDaysAgo=1)
    assert_true(str(yesterday)[:10] < DateTimeTool.getNowDate(), '昨日日期应小于今日: %s' % yesterday)
    wd = DateTimeTool.getWeekDay()
    assert_true(bool(str(wd).strip()), 'getWeekDay 返回为空')
    return 'now=%s 时间戳往返OK 昨日=%s 星期=%s' % (now, yesterday, wd)


@check('common.fileTool', 'common/fileTool.py', '文件工具：写读 JSON/追加/替换/截断/目录清理')
def _():
    from common.fileTool import FileTool
    with tmp_workdir() as d:
        f = os.path.join(d, 'data.json')
        FileTool.writeObjectIntoFile({'k': 'v', 'n': 1}, f)
        obj = FileTool.readJsonFromFile(f)
        assert_true(obj == {'k': 'v', 'n': 1}, 'JSON 往返不一致: %r' % obj)
        txt = os.path.join(d, 'a.txt')
        with open(txt, 'w') as fh:
            fh.write('hello\n')
        FileTool.appendContent(txt, 'world')
        with open(txt) as fh:
            assert_true('world' in fh.read(), 'appendContent 未追加成功')
        FileTool.replaceFileContent(txt, 'hello', 'HELLO')
        with open(txt) as fh:
            assert_true('HELLO' in fh.read(), 'replaceFileContent 未替换成功')
        chardet = FileTool.getChardet(txt)
        assert_true(chardet is not None, 'getChardet 返回空')
        sub = os.path.join(d, 'sub')
        os.mkdir(sub)
        with open(os.path.join(sub, 'x.tmp'), 'w') as fh:
            fh.write('x')
        FileTool.truncateDir(sub)
        assert_true(len(os.listdir(sub)) == 0, 'truncateDir 未清空目录')
    return 'JSON 往返/追加/替换/编码探测/目录清理 全部通过'


@check('common.strTool', 'common/strTool.py', '字符串工具：边界提取/UUID/JSON/随机文本/前后缀')
def _():
    from common.strTool import StrTool
    assert_true(StrTool.getStringWithLBRB('a<foo>b', '<', '>') == 'foo', '边界提取失败')
    u = StrTool.addUUID('p')
    assert_true(u.startswith('p_'), 'addUUID 前缀异常: %r' % u)
    assert_true('"a"' in StrTool.objectToJsonStr({'a': 1}), 'objectToJsonStr 输出异常')
    fixed = StrTool.addFix('mid', True, 'pre_', True, '_suf')
    assert_true(fixed == 'pre_mid_suf', 'addFix 异常: %r' % fixed)
    assert_true(len(StrTool.getSpecifiedStr(8, 'x')) == 8, 'getSpecifiedStr 长度不符')
    text = StrTool.getRandomText(10)
    assert_true(len(text) == 10, 'getRandomText 长度不符: %r' % text)
    d = StrTool.contentToDict('k1=v1\nk2=v2')
    assert_true(d['k1']['value'] == 'v1' and d['k2']['value'] == 'v2', 'contentToDict 解析异常: %r' % d)
    return '边界提取=%s 随机文本=%s 字典解析OK' % ('foo', text)


@check('common.assertTool', 'common/assertTool.py', '断言工具：正则匹配/文件相等/文件大小相等')
def _():
    from common.assertTool import AssertTool
    with tmp_workdir() as d:
        f1, f2 = os.path.join(d, '1.txt'), os.path.join(d, '2.txt')
        for f, content in ((f1, 'same-content'), (f2, 'same-content')):
            with open(f, 'w') as fh:
                fh.write(content)
        assert_true(AssertTool.isRegularMatch('Abc123', '^[A-Za-z0-9]+$'), '正则匹配误判')
        assert_true(not AssertTool.isRegularMatch('Abc123!', '^[A-Za-z0-9]+$'), '正则匹配误判(应不匹配)')
        assert_true(AssertTool.isFilesEqual(f1, f2), '相同内容文件应判定相等')
        assert_true(AssertTool.isFilesSizeEqual(f1, f2), '相同大小文件应判定相等')
        with open(f2, 'w') as fh:
            fh.write('different!')
        assert_true(not AssertTool.isFilesEqual(f1, f2), '不同内容文件应判定不等')
    return '正则/文件相等/大小相等 正反用例全部通过'


@check('common.network', 'common/network.py', '网络工具：本机 IP 获取')
def _():
    from common.network import Network
    ip = Network.get_local_ip()
    assert_true(ip and re_check_ip(ip), '本机 IP 异常: %r' % ip)
    return '本机 IP=%s' % ip


def re_check_ip(ip):
    import re
    return bool(re.match(r'^\d{1,3}(\.\d{1,3}){3}$', str(ip)))


@check('common.custom_multiprocessing', 'common/custom_multiprocessing.py', '自定义进程池：异步任务分发与回收')
def _():
    from common.custom_multiprocessing import Custom_Pool
    from dbg_pool_task import pool_task
    pool = Custom_Pool(2)
    async_results = [pool.apply_async(pool_task, (i,)) for i in (10, 32)]
    pool.close()
    pool.join()
    values = [r.get(timeout=30) for r in async_results]
    assert_true(values == [20, 64], '进程池结果异常: %r' % values)
    return '双任务并行结果 %r' % values


@check('common.pytest', 'common/pytest.py', 'pytest 配置处理：pytest.ini 生成幂等')
def _():
    from common.pytest import deal_pytest_ini_file
    ini = os.path.join('config', 'pytest.ini')
    before = open(ini, 'rb').read() if os.path.exists(ini) else None
    deal_pytest_ini_file()
    assert_true(os.path.exists(ini), 'pytest.ini 未生成')
    after = open(ini, 'rb').read()
    if before is not None:
        assert_true(before == after, 'pytest.ini 内容被意外改写')
    return 'config/pytest.ini 就绪且幂等（%d 字节）' % len(after)


@check('common.java.javaTools', 'common/java/javaTools.py', 'Java 工具：jar 扫描与 JVM classpath 构建')
def _():
    setup_java_home()
    from common.java.javaTools import JavaTool
    jars = JavaTool.getAllJar().split(':')
    assert_true(len(jars) >= 10, '扫描到的 jar 数量异常: %d' % len(jars))
    names = [os.path.basename(j) for j in jars]
    assert_true(any('tess4j' in n for n in names), '缺少 tess4j jar')
    assert_true(any('captchaRecognition' in n for n in names), '缺少 captchaRecognition jar')
    return 'classpath 含 %d 个 jar，tess4j/captchaRecognition 就绪' % len(jars)


@check('common.captchaRecognitionTool', 'common/captchaRecognitionTool.py', '验证码识别：JVM 启动 + OCR 全链路（本地生成样图）')
def _():
    setup_java_home()
    try:
        import jpype
    except Exception as e:
        raise Skip('jpype 未安装: %s' % e)
    try:
        from PIL import Image, ImageDraw
    except Exception as e:
        raise Skip('Pillow 未安装，无法生成样图: %s' % e)
    from common.captchaRecognitionTool import CaptchaRecognitionTool
    with tmp_workdir() as d:
        img_path = os.path.join(d, 'captcha.png')
        im = Image.new('RGB', (160, 60), 'white')
        ImageDraw.Draw(im).text((30, 20), '1234', fill='black')
        im.save(img_path)
        try:
            result = CaptchaRecognitionTool().captchaRecognition(img_path, 'eng')
        except Exception as e:
            if 'UnsatisfiedLinkError' in str(e) or 'Unable to load library' in str(e):
                raise Skip('缺 tesseract 本地动态库（macOS: brew install tesseract）；'
                           'Java classpath 与类加载已验证通过，OCR 原生绑定属环境依赖')
            raise
        assert_true(result is not None, '识别接口返回 None')
    return 'JVM+OCR 全链路执行成功，识别输出=%r' % (result,)


@check('common.hamcrest', 'common/hamcrest/hamcrest.py', '断言匹配器：30+ 匹配方法抽样验证（含失败必须抛断言）')
def _():
    from common.hamcrest.hamcrest import assert_that
    assert_that(1).is_equal_to(1)
    assert_that(1).is_not_equal_to(2)
    assert_that('abc').is_length(3)
    assert_that(None).is_none()
    assert_that('x').is_not_none()
    assert_that('').is_empty()
    assert_that('x').is_not_empty()
    assert_that(1.05).is_close_to(1.0, 0.1)
    assert_that(2).is_greater_than(1)
    assert_that(1).is_greater_than_or_equal_to(1)
    assert_that(1).is_less_than(2)
    assert_that('hello world').contains('world')
    assert_that('hello').does_not_contains('xyz')
    assert_that('hello').starts_with('he')
    assert_that('hello').ends_with('lo')
    assert_that('AB').is_equal_to_ignoring_case('ab')
    assert_that('abc123').is_match_by_regexp(r'^\w+\d+$')
    assert_that(True).is_true()
    assert_that(False).is_false()
    assert_that(1).is_in([1, 2])
    assert_that(3).is_not_in([1, 2])
    assert_that([1]).is_has_item(1)
    assert_that({'a': 1}).contains_key('a')
    assert_that({'a': 1}).contains_value(1)
    assert_that({'a': 1}).contains_entry('a', 1)
    raised = 0
    for bad in (lambda: assert_that(1).is_equal_to(2),
                lambda: assert_that('a').is_empty(),
                lambda: assert_that(True).is_false()):
        try:
            bad()
        except AssertionError:
            raised += 1
    assert_true(raised == 3, '反向断言应抛 AssertionError，实际抛出 %d/3' % raised)
    return '正向 26 项 + 反向 3 项全部符合预期'


@check('common.hamcrest.custom_matchers', 'common/hamcrest/custom_matchers.py', '自定义匹配器：h_is_true / h_is_empty')
def _():
    from hamcrest import assert_that as h_assert_that
    from common.hamcrest.custom_matchers import h_is_true, h_is_empty
    h_assert_that(True, h_is_true())
    h_assert_that('', h_is_empty())
    raised = 0
    for bad in (lambda: h_assert_that(False, h_is_true()),
                lambda: h_assert_that('x', h_is_empty())):
        try:
            bad()
        except AssertionError:
            raised += 1
    assert_true(raised == 2, '反向用例应抛 AssertionError，实际抛出 %d/2' % raised)
    return 'h_is_true/h_is_empty 正反向用例通过'
