#!usr/bin/env python
#-*- coding:utf-8 -*-
"""
@author: Jeff Zhang
@date:   2017-08-23
"""

from news_spider.items import NewsItem

from scrapy.contrib.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.contrib.linkextractors.lxmlhtml import LxmlLinkExtractor
from scrapy.selector import Selector
import json
import re
from scrapy import Request
import time

def ListCombiner(lst):
    string = ""
    for e in lst:
        string += e
    return string.replace(' ','').replace('\n','').replace('\t','')\
        .replace('\xa0','').replace('\u3000','').replace('\r','')


class NeteaseNewsSpider(CrawlSpider):
    name = "netease_news_spider"
    start_urls = ['http://news.163.com/']

    # Spider中间件会对Spider发出的request进行检查，只有满足allow_domain才会被允许发出
    allowed_domains = ['news.163.com']


    # http://news.163.com/17/0823/20/CSI5PH3Q000189FH.html
    url_pattern = r'(http://news\.163\.com)/(\d{2})/(\d{4})/\d+/(\w+)\.html'
    rules = [
        Rule(LxmlLinkExtractor(allow=[url_pattern]), callback='parse_news', follow=True)
    ]

    '''
    1. 因为使用的yield，而不是return。parse函数将会被当做一个生成器使用。scrapy会逐一获取parse方法中生成的结果，并判断该结果是一个什么样的类型；
    2. 如果是request则加入爬取队列，如果是item类型则使用pipeline处理，其他类型则返回错误信息。
    3. scrapy取到第一部分的request不会立马就去发送这个request，只是把这个request放到队列里，然后接着从生成器里获取；
    4. 取尽第一部分的request，然后再获取第二部分的item，取到item了，就会放到对应的pipeline里处理；
    5. parse()方法作为回调函数(callback)赋值给了Request，指定parse()方法来处理这些请求 scrapy.Request(url, callback=self.parse)
    6. Request对象经过调度，执行生成 scrapy.http.response()的响应对象，并送回给parse()方法，直到调度器中没有Request（递归的思路）
    7. 取尽之后，parse()工作结束，引擎再根据队列和pipelines中的内容去执行相应的操作；
    8. 程序在取得各个页面的items前，会先处理完之前所有的request队列里的请求，然后再提取items。
    9. 这一切的一切，Scrapy引擎和调度器将负责到底。
    '''

    def parse_news(self, response):
        sel = Selector(response)
        pattern = re.match(self.url_pattern, str(response.url))
        source = 'news.163.com'
        if sel.xpath('//div[@class="post_time_source"]/text()'):
            time_ = sel.xpath('//div[@class="post_time_source"]/text()').extract_first().split()[0] + ' ' + sel.xpath('//div[@class="post_time_source"]/text()').extract_first().split()[1]
        else:
            time_ = 'unknown'
        date = '20' + pattern.group(2) + '/' + pattern.group(3)[0:2] + '/' + pattern.group(3)[2:]
        newsId = pattern.group(4)
        url = response.url
        title = sel.xpath("//h1/text()").extract()[0]
        contents = ListCombiner(sel.xpath('//p/text()').extract()[2:-3])
        comment_url = 'http://comment.news.163.com/api/v1/products/a2869674571f77b5a0867c3d71db5856/threads/{}'.format(newsId)

        # yield is a keyword that is used like return, except the function will return a generator.
        yield Request(comment_url, self.parse_comment, meta={'source':source,
                                                             'date':date,
                                                             'newsId':newsId,
                                                             'url':url,
                                                             'title':title,
                                                             'contents':contents,
                                                             'time':time_
                                                             })

    def parse_comment(self, response):
        result = json.loads(response.text)
        item = NewsItem()
        item['source'] = response.meta['source']
        item['date'] = response.meta['date']
        item['newsId'] = response.meta['newsId']
        item['url'] = response.meta['url']
        item['title'] = response.meta['title']
        item['contents'] = response.meta['contents']
        item['comments'] = result['cmtAgainst'] + result['cmtVote'] + result['rcount']
        item['time'] = response.meta['time']
        return item



class SinaNewsSpider(CrawlSpider):
    name = "sina_news_spider"
    allowed_domains = ['news.sina.com.cn']
    start_urls = ['http://news.sina.com.cn']
    # http://finance.sina.com.cn/review/hgds/2017-08-25/doc-ifykkfas7684775.shtml
    # url_pattern = r'(http://(?:\w+\.)*news\.sina\.com\.cn)/.*/(\d{4}-\d{2}-\d{2})/doc-(.*)\.shtml'
    today_date = time.strftime('%Y-%m-%d',time.localtime(time.time()))
    url_pattern = r'(http://(?:\w+\.)*news\.sina\.com\.cn)/.*/({})/doc-(.*)\.shtml'.format(today_date)

    rules = [
        Rule(LxmlLinkExtractor(allow=[url_pattern]), callback='parse_news', follow=True)
    ]

    def parse_news(self, response):
        sel = Selector(response)
        if sel.xpath("//h1[@id='artibodyTitle']/text()"):
            title = sel.xpath("//h1[@id='artibodyTitle']/text()").extract()[0]
            pattern = re.match(self.url_pattern, str(response.url))
            source = pattern.group(1)
            date = pattern.group(2).replace('-','/')
            if sel.xpath('//span[@class="time-source"]/text()'):
                time_ = sel.xpath('//span[@class="time-source"]/text()').extract_first().split()[0]
            else:
                time_ = 'unknown'
            newsId = pattern.group(3)
            url = response.url
            contents = ListCombiner(sel.xpath('//p/text()').extract()[:-3])
            comment_elements = sel.xpath("//meta[@name='sudameta']").xpath('@content').extract()[1]
            comment_channel = comment_elements.split(';')[0].split(':')[1]
            comment_id = comment_elements.split(';')[1].split(':')[1]
            comment_url = 'http://comment5.news.sina.com.cn/page/info?version=1&format=js&channel={}&newsid={}'.format(comment_channel,comment_id)

            yield Request(comment_url, self.parse_comment, meta={'source':source,
                                                                 'date':date,
                                                                 'newsId':newsId,
                                                                 'url':url,
                                                                 'title':title,
                                                                 'contents':contents,
                                                                 'time':time_
                                                                })

    def parse_comment(self, response):
        if re.findall(r'"total": (\d*)\,', response.text):
            comments = re.findall(r'"total": (\d*)\,', response.text)[0]
        else:
            comments = 0
        item = NewsItem()
        item['comments'] = comments
        item['title'] = response.meta['title']
        item['url'] = response.meta['url']
        item['contents'] = response.meta['contents']
        item['source'] = response.meta['source']
        item['date'] = response.meta['date']
        item['newsId'] = response.meta['newsId']
        item['time'] = response.meta['time']
        return item


class TencentNewsSpider(CrawlSpider):
    name = 'tencent_news_spider'
    # allowed_domains = ['news.qq.com']
    start_urls = ['http://news.qq.com']
    # http://news.qq.com/a/20170825/026956.htm
    url_pattern = r'(.*)/a/(\d{8})/(\d+)\.htm'
    rules = [
        Rule(LxmlLinkExtractor(allow=[url_pattern]), callback='parse_news', follow=True)
    ]

    def parse_news(self, response):
        sel = Selector(response)
        if sel.xpath('//*[@id="Main-Article-QQ"]/div/div[1]/div[1]/div[1]/h1/text()'):
            title = sel.xpath('//*[@id="Main-Article-QQ"]/div/div[1]/div[1]/div[1]/h1/text()').extract()[0]
        elif sel.xpath('//*[@id="C-Main-Article-QQ"]/div/div[1]/div[1]/div[1]/h1/text()'):
            title = sel.xpath('//*[@id="C-Main-Article-QQ"]/div/div[1]/div[1]/div[1]/h1/text()').extract()[0]
        elif sel.xpath('//*[@id="ArticleTit"]/text()'):
            title = sel.xpath('//*[@id="ArticleTit"]/text()').extract()[0]
        else:
            title = 'unknown'
        pattern = re.match(self.url_pattern, str(response.url))
        source = pattern.group(1)
        date = pattern.group(2)
        date = date[0:4] + '/' + date[4:6] + '/' + date[6:]
        newsId = pattern.group(3)
        url = response.url
        if sel.xpath('//*[@id="Main-Article-QQ"]/div/div[1]/div[1]/div[1]/div/div[1]/span[3]/text()'):
            time_ = sel.xpath('//*[@id="Main-Article-QQ"]/div/div[1]/div[1]/div[1]/div/div[1]/span[3]/text()').extract()[0]
        else:
            time_ = 'unknown'
        contents = ListCombiner(sel.xpath('//p/text()').extract()[:-8])

        if response.xpath('//*[@id="Main-Article-QQ"]/div/div[1]/div[2]/script[2]/text()'):
            cmt = response.xpath('//*[@id="Main-Article-QQ"]/div/div[1]/div[2]/script[2]/text()').extract()[0]
            if re.findall(r'cmt_id = (\d*);', cmt):
                cmt_id = re.findall(r'cmt_id = (\d*);', cmt)[0]
                comment_url = 'http://coral.qq.com/article/{}/comment?commentid=0&reqnum=1&tag=&callback=mainComment&_=1389623278900'.format(cmt_id)
                yield Request(comment_url, self.parse_comment, meta={'source': source,
                                                                     'date': date,
                                                                     'newsId': newsId,
                                                                     'url': url,
                                                                     'title': title,
                                                                     'contents': contents,
                                                                     'time': time_
                                                                     })
            else:
                item = NewsItem()
                item['source'] = source
                item['time'] = time_
                item['date'] = date
                item['contents'] = contents
                item['title'] = title
                item['url'] = url
                item['newsId'] = newsId
                item['comments'] = 0
                return item

    def parse_comment(self, response):
        if re.findall(r'"total":(\d*)\,', response.text):
            comments = re.findall(r'"total":(\d*)\,', response.text)[0]
        else:
            comments = 0
        item = NewsItem()
        item['source'] = response.meta['source']
        item['time'] = response.meta['time']
        item['date'] = response.meta['date']
        item['contents'] = response.meta['contents']
        item['title'] = response.meta['title']
        item['url'] = response.meta['url']
        item['newsId'] = response.meta['newsId']
        item['comments'] = comments
        return item


class SohuNewsSpider(CrawlSpider):
    name = "sohu_news_spider"
    pass



class IfengNewsSpider(CrawlSpider):
    name = "ifeng_news_spider"
    pass


