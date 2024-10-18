import asyncio
from bs4 import BeautifulSoup
import time
import random
from pyppeteer import launch
from util.common_util import CommonUtil
from util.llm_util import LLMUtil
from util.oss_util import OSSUtil
from util.checkdata_util import CheckUtil
from logger_config import setup_logger  # 导入日志配置

#设置日志记录
logger = setup_logger()
llm = LLMUtil()
oss = OSSUtil()
check = CheckUtil()

global_agent_headers = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36 Edg/116.0.1938.54",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36 OPR/102.0.4880.95",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 12; Mobile; LG; Nexus 5X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Mobile Safari/537.36"
]

class WebsitCrawler:
    def __init__(self):
        self.browser = None
    
    '''
    description: 打开网页获取网页内容
    param {*} self
    param {*} url 网址
    return {*} soup: 网站html结构 screenshot_key: 网站截图 thumnbail_key: 网站缩略图截图
    '''
    async def obtain_html_data(self, url):
        # 检查并启动浏览器
        if self.browser is None:
            self.browser = await launch(headless=True,
                                        ignoreDefaultArgs=["--enable-automation"],
                                        ignoreHTTPSErrors=True,
                                        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                                                '--disable-software-rasterizer', '--disable-setuid-sandbox'],
                                        handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False)
        # 打开新页面
        page = await self.browser.newPage()
        try:
            # 设置用户代理
            await page.setUserAgent(random.choice(global_agent_headers))
            # 设置页面视口大小并访问具体URL
            width = 1920  # 默认宽度为 1920
            height = 1080  # 默认高度为 1080
            await page.setViewport({'width': width, 'height': height})

            # 页面重试机制
            max_retries = 3
            retry_delay = 2 
            for attempt in range(max_retries):
                try:
                    response =  await page.goto(url, {'timeout': 70000, 'waitUntil': ['load', 'networkidle0']})
                    if response is None:
                        return {'error': '页面加载失败，无响应'}
                except Exception as e:
                    logger.info(f'页面加载超时, 尝试重新加载 (尝试次数: {attempt + 1}/{max_retries}): {e}')
                    if attempt == max_retries - 1:
                        logger.error(f'页面加载超时, 达到最大重试次数: {e}')
                        return None
                    await asyncio.sleep(retry_delay)

            # 等待页面加载，提高获取页面的质量
            await page.waitForSelector('body')

            origin_content = await page.content()
            soup = BeautifulSoup(origin_content, 'html.parser')
            
            # 获取网站截图信息
            image_key = oss.get_default_file_key(url)
            dimensions = await page.evaluate(f'''(width, height) => {{
                return {{
                    width: {width},
                    height: {height},
                    deviceScaleFactor: window.devicePixelRatio
                }};
            }}''', width, height)
            
            screenshot_path = './' + url.replace("https://", "").replace("http://", "").replace("/", "").replace(".",
                                                                                                                 "-") + '.png'
            await page.screenshot({'path': screenshot_path, 'clip': {
                'x': 0,
                'y': 0,
                'width': dimensions['width'],
                'height': dimensions['height']
            }})

            screenshot_key = oss.upload_file_to_r2(screenshot_path, image_key)

            thumnbail_key = oss.generate_thumbnail_image(url, image_key)
            return soup, screenshot_key, thumnbail_key
        except Exception as e:
            logger.error(f"获取网页内容时发生错误: {e}")
            return None
        finally:
            await page.close() 
    
    '''
    description: 获取网站所有数据
    param {*} self
    param {*} url 网址
    param {*} tags 二级标签
    param {*} languages 多语言数组
    return {*}
    '''  
    async def scrape_website(self, url, languages, whetheriImage=True,):
        try:
            # 记录程序开始时间
            start_time = int(time.time())
            logger.info("正在处理：" + url)
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url

            if self.browser is None:
                self.browser = await launch(headless=True,
                                            ignoreDefaultArgs=["--enable-automation"],
                                            ignoreHTTPSErrors=True,
                                            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                                                  '--disable-software-rasterizer', '--disable-setuid-sandbox'],
                                            handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False)

            page = await self.browser.newPage()

            # 设置用户代理
            await page.setUserAgent(random.choice(global_agent_headers))

            # 设置页面视口大小并访问具体URL
            width = 1920  # 默认宽度为 1920
            height = 1080  # 默认高度为 1080
            await page.setViewport({'width': width, 'height': height})
            max_retries = 3
            retry_delay = 2 

            # 页面加载重试
            for attempt in range(max_retries):
                try:
                    response =  await page.goto(url, {'timeout': 70000, 'waitUntil': ['load', 'networkidle0']})
                    if response is None:
                        return {'error': '页面加载失败，无响应'}
                except Exception as e:
                    logger.info(f'页面加载超时, 尝试重新加载 (尝试次数: {attempt + 1}/{max_retries}): {e}')
                    if attempt == max_retries - 1:
                        logger.error(f'页面加载超时, 达到最大重试次数: {e}')
                        return {'error': '页面加载超时, 达到最大重试次数: {e}'}
                    await asyncio.sleep(retry_delay)
            
            # 等待页面加载，提高获取页面的质量
            await page.waitFor(5000)

            # 获取网页内容
            origin_content = await page.content()
            soup = BeautifulSoup(origin_content, 'html.parser')

            title = soup.title.string.strip() if soup.title else ''
            if not title:
                title = check.check_title(llm.process_title(url))
            # 根据url提取域名生成name

            name = CommonUtil.get_name_by_url(url)

            # 获取网页描述
            description = ''
            meta_description = soup.find('meta', attrs={'name': 'description'})
            if meta_description:
                description = meta_description['content'].strip()
            if not description:
                meta_description = soup.find('meta', attrs={'property': 'og:description'})
                description = meta_description['content'].strip()
            if not description:
                description = check.check_description(llm.process_description(url))
            
            logger.info(f"url:{url}, title:{title},description:{description}")

            if whetheriImage:
                #  生成网站截图
                image_key = oss.get_default_file_key(url)
                dimensions = await page.evaluate(f'''(width, height) => {{
                    return {{
                        width: {width},
                        height: {height},
                        deviceScaleFactor: window.devicePixelRatio
                    }};
                }}''', width, height)
                
                # 截屏并设置图片大小
                screenshot_path = './' + url.replace("https://", "").replace("http://", "").replace("/", "").replace(".",
                                                                                                                    "-") + '.png'
                await page.screenshot({'path': screenshot_path, 'clip': {
                    'x': 0,
                    'y': 0,
                    'width': dimensions['width'],
                    'height': dimensions['height']
                }})

                # 上传图片，返回图片地址
                screenshot_key = oss.upload_file_to_r2(screenshot_path, image_key)

                # 生成缩略图
                thumnbail_key = oss.generate_thumbnail_image(url, image_key)
            else:
                screenshot_key="http://exampscreenshot_key"
                thumnbail_key="http://exampthumnbail_key"

            # 抓取整个网页内容
            content = soup.get_text()

            # return;
            
            detail = check.check_detail(llm.process_detail(content))
            
            introduction = check.check_introduction(llm.process_introduction(content))
                
            features = check.check_feature(llm.process_features(content))

            if not all([title, description, detail, introduction, features]):
                logger.error(f"URL: {url} - 数据有空值，返回错误")
                return {'error': '处理失败：一个或多个字段为空'}
                
            await page.close()

            # 循环languages数组
            processed_languages = []

            if not all([title, description, detail, introduction, features]):
                logger.warning(f"URL: {url} - 一个或多个字段为空，跳过多语言处理")
                return {'error': '有数据不全，返回错误'}
            
            if languages:
                for language in languages:
                    logger.info("正在处理" + url + "站点，生成" + language + "语言")
                    processed_title = check.check_language(language, llm.process_language(language, title))
                    
                    processed_description = check.check_language(language, llm.process_language(language, description))
                    
                    processed_detail = check.check_language(language, llm.process_language(language, detail))
                    
                    processed_introduction = check.check_language(language, llm.process_language(language, introduction))
                    
                    processed_features = check.check_language(language, llm.process_language(language, features))

                    processed_languages.append({'language': language, 'title': processed_title,
                                                'description': processed_description, 'detail': processed_detail,
                                                'introduction': processed_introduction, 'features': processed_features})
            

            logger.info(url + "站点处理成功")
            return {
                'name': name,
                'url': url,
                'title': title,
                'description': description,
                'features': features,
                'detail': detail,
                'introduction': introduction,
                'screenshot_data': screenshot_key,
                'screenshot_thumbnail_data': thumnbail_key,
                'languages': processed_languages,
            }
        except Exception as e:
            logger.error("处理" + url + "站点异常，错误信息:", e)
            return None
        finally:
            # 计算程序执行时间
            execution_time = int(time.time()) - start_time

            # 输出程序执行时间
            logger.info("处理" + url + "用时：" + str(execution_time) + " 秒")


    async def scrape_website_detail(self, url, languages):
        try:
            start_time = int(time.time())
            logger.info("正在处理详情：" + url)
            
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url

            if self.browser is None:
                self.browser = await launch(headless=True,
                                            ignoreDefaultArgs=["--enable-automation"],
                                            ignoreHTTPSErrors=True,
                                            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                                                  '--disable-software-rasterizer', '--disable-setuid-sandbox'],
                                            handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False)

            page = await self.browser.newPage()
            await page.setUserAgent(random.choice(global_agent_headers))

            await page.setViewport({'width': 1920, 'height': 1080})
            
            response = await page.goto(url, {'timeout': 70000, 'waitUntil': ['load', 'networkidle2']})
            
            if response is None:
                return {'error': '页面加载失败，无响应'}

            # await self.handle_response(response)

            origin_content = await page.content()
            soup = BeautifulSoup(origin_content, 'html.parser')

            content = soup.get_text()
            
            detail = llm.process_detail(content)
            if not detail:
                logger.info(url + "站点处理detail为空，正在重试")
                detail = llm.process_detail(content)

            await page.close()
            
            processed_languages = []
            if languages:
                for language in languages:
                    logger.info(f"正在处理{url}站点，生成{language}语言的detail")
                    processed_detail = llm.process_language(language, detail)
                    processed_languages.append({'language': language, 'detail': processed_detail})
            
            logger.info(url + "站点详情处理成功")
            return {
                'url': url,
                'detail': detail,
                'languages': processed_languages
            }
        except Exception as e:
            logger.error("处理" + url + "站点详情异常，错误信息:", e)
            return None
        finally:
            execution_time = int(time.time()) - start_time
            logger.info("处理" + url + "详情用时：" + str(execution_time) + " 秒")


    async def scrape_website_introduction(self, url, languages=None):
        try:
            start_time = int(time.time())
            logger.info("正在处理简介：" + url)
            
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url

            if self.browser is None:
                self.browser = await launch(headless=True,
                                            ignoreDefaultArgs=["--enable-automation"],
                                            ignoreHTTPSErrors=True,
                                            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                                                  '--disable-software-rasterizer', '--disable-setuid-sandbox'],
                                            handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False)

            page = await self.browser.newPage()
            await page.setUserAgent(random.choice(global_agent_headers))

            await page.setViewport({'width': 1920, 'height': 1080})
            
            response = await page.goto(url, {'timeout': 70000, 'waitUntil': ['load', 'networkidle2']})
            
            if response is None:
                return {'error': '页面加载失败，无响应'}

            # await self.handle_response(response)

            origin_content = await page.content()
            soup = BeautifulSoup(origin_content, 'html.parser')

            content = soup.get_text()
            
            introduction = llm.process_introduction(content)
            if not introduction:
                logger.info(url + "站点处理introduction为空，正在重试")
                introduction = llm.process_introduction(content)

            await page.close()

            if not introduction:
                logger.warning(f"URL: {url} - introduction处理失败")
                return {'error': 'introduction处理失败'}

            processed_languages = []
            if languages:
                for language in languages:
                    logger.info(f"正在处理{url}站点，生成{language}语言的introduction")
                    processed_introduction = llm.process_language(language, introduction)
                    processed_languages.append({'language': language, 'introduction': processed_introduction})

            logger.info(url + "站点简介处理成功")
            return {
                'url': url,
                'introduction': introduction,
                'languages': processed_languages
            }
        except Exception as e:
            logger.error("处理" + url + "站点简介异常，错误信息:", e)
            return None
        finally:
            execution_time = int(time.time()) - start_time
            logger.info("处理" + url + "简介用时：" + str(execution_time) + " 秒")
    
    
    async def scrape_feature(self, url, languages=None):
        try:
            start_time = int(time.time())
            logger.info("正在处理网站特性：" + url)
            
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url

            if self.browser is None:
                self.browser = await launch(headless=True,
                                            ignoreDefaultArgs=["--enable-automation"],
                                            ignoreHTTPSErrors=True,
                                            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                                                  '--disable-software-rasterizer', '--disable-setuid-sandbox'],
                                            handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False)

            page = await self.browser.newPage()
            await page.setUserAgent(random.choice(global_agent_headers))

            await page.setViewport({'width': 1920, 'height': 1080})
            
            response = await page.goto(url, {'timeout': 70000, 'waitUntil': ['load', 'networkidle2']})
            
            if response is None:
                return {'error': '页面加载失败，无响应'}

            # await self.handle_response(response)

            origin_content = await page.content()
            soup = BeautifulSoup(origin_content, 'html.parser')

            content = soup.get_text()
            
            features = llm.process_features(content)
            if not features:
                logger.info(url + "站点处理features为空，正在重试")
                features = llm.process_features(content)

            await page.close()

            if not features:
                logger.warning(f"URL: {url} - features处理失败")
                return {'error': 'features处理失败'}

            processed_languages = []
            if languages:
                for language in languages:
                    logger.info(f"正在处理{url}站点，生成{language}语言的features")
                    processed_introduction = llm.process_language(language, features)
                    processed_languages.append({'language': language, 'features': processed_introduction})

            logger.info(url + "站点简介处理成功")
            return {
                'url': url,
                'features': features,
                'languages': processed_languages
            }
        except Exception as e:
            logger.error("处理" + url + "站点简介异常，错误信息:", e)
            return None
        finally:
            execution_time = int(time.time()) - start_time
            logger.info("处理" + url + "特性用时：" + str(execution_time) + " 秒")

