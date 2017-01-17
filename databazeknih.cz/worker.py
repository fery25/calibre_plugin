#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
						print_function)

__license__   = 'GPL v3'
__copyright__ = '2017, Frantisek Lorenc <franta.lorenc@gmail.com>'
__copyright__ = 'based od Pavel Skulil <pavelsku@gmail.com>'
__docformat__ = 'restructuredtext cs'

import socket, re
from threading import Thread
from calibre.ebooks.metadata.book.base import Metadata
import lxml, sys
import lxml.html as lh
from calibre.utils.date import utcnow
from datetime import datetime
from dateutil import parser
from calibre.ebooks.metadata import MetaInformation, check_isbn
from calibre import browser


class Worker(Thread): # Get details
	isbn = None
	'''
	Get book details from antikvarium.hu book page in a separate thread
	'''

	def __init__(self, url, result_queue, browser, log, relevance, plugin, timeout=20):
		Thread.__init__(self)
		self.daemon = True
		self.url, self.result_queue = url, result_queue
		self.log, self.timeout = log, timeout
		self.relevance, self.plugin = relevance, plugin
		self.browser = browser.clone_browser()
		self.cover_url = self.databazeknih_id = None #self.isbn = None

	def run(self):
		self.log.info('worker jede')
		try:
			self.get_details()
		except:
			self.log.exception('get_details failed for url: %r'%self.url)

	def get_details(self):
		
		try:
#			self.log.info('Get details:%s'%self.url)
			raw = self.browser.open_novisit(self.url, timeout=self.timeout)#.read().strip()
		except Exception as e:
			if callable(getattr(e, 'getcode', None)) and \
					e.getcode() == 404:
				self.log.error('URL malformed: %r'%self.url)
				return
			attr = getattr(e, 'args', [None])
			attr = attr if attr else [None]
			if isinstance(attr[0], socket.timeout):
				msg = 'Databazeknih timed out. Try again later.'
				self.log.error(msg)
			else:
				msg = 'Failed to make details query: %r'%self.url
				self.log.exception(msg)
			return

		root = lh.parse(raw)
		self.parse_details(root)

	def parse_details(self, root):
		search_data = ''
		isbn = None
		
		try:
			self.log.info('Parse details:%s'%self.url)
			databazeknih_id = self.parse_databazeknih_id(self.url)
			self.log.info('Parsed DK identifier:%s'%databazeknih_id)
		except:
			self.log.exception('Error parsing databazeknih id for url: %r'%self.url)
			databazeknih_id = None

#		self.log.info('11')
		try:
			title = self.parse_title(root)
			self.log.info('Parsed title:%s'%title)
		except:
			self.log.exception('Error parsing title for url: %r'%self.url)
			title = None
		
		try:
			authors = self.parse_authors(root)
			self.log.info('Parsed authors:%s'%authors)
		except:
			self.log.exception('Error parsing authors for url: %r'%self.url)
			authors = []

		if not title or not authors or not databazeknih_id:
			self.log.error('Could not find title/authors/databazeknih id for %r'%self.url)
			self.log.error('DK id: %r Title: %r Authors: %r'%(databazeknih_id, title, authors))
			return

		mi = Metadata(title, authors)
		self.log.info('dbki:%s'%databazeknih_id)
		mi.set_identifier('databazeknih', databazeknih_id)
		self.databazeknih_id = databazeknih_id

		try:
			(mi.series, mi.series_index) = self.parse_series(root)
			self.log.info('Parsed series:%s'%mi.series)
			self.log.info('Parsed series index:%s'%mi.series_index)
		except :
			self.log.exception('Error parsing series for url: %r'%self.url)
			series = None
			
		try:
			mi.comments = self.parse_comments(root)
			self.log.info('Parsed comments:%s'%mi.comments)
		except:
			self.log.exception('Error parsing comments for url: %r'%self.url)

		try:
			self.cover_url = self.parse_cover(root)
			self.log.info('Parsed URL for cover:%r'%self.cover_url)
			self.plugin.cache_identifier_to_cover_url(self.databazeknih_id, self.cover_url)
		except:
			self.log.exception('Error parsing cover for url: %r'%self.url)
		mi.has_cover = bool(self.cover_url)

		try:
			mi.tags = self.parse_tags(root)
			self.log.info('Parsed tags:%s'%mi.tags)
		except:
			self.log.exception('Error parsing tags for url: %r'%self.url)
			
		try:
			mi.publisher = self.parse_publisher(root)
			self.log.info('Parsed publisher:%s'%mi.publisher)
		except:
			self.log.exception('Error parsing publisher for url: %r'%self.url)
			
		try:
			mi.pubdate = self.parse_pubdate(root)
			self.log.info('Parsed pubdate:%s'%mi.pubdate)
		except:
			self.log.exception('Error parsing pubdate for url: %r'%self.url)

			
		try:
			mi.rating = self.parse_rating(root)
			self.log.info('Parsed rating:%s'%mi.rating)
		except:
			self.log.exception('Error parsing rating for url: %r'%self.url)

		mi.source_relevance = self.relevance

#		if series:
#			mi.series = series
		
		try:
			isbn = self.parse_isbn(root)
			if isbn:
				self.isbn = mi.isbn = isbn
		except:
			self.log.exception('Error parsing ISBN for url: %r'%self.url)

		if self.databazeknih_id:
			self.plugin.cache_isbn_to_identifier(self.isbn, self.databazeknih_id)
			
#		self.plugin.clean_downloaded_metadata(mi)
#		mi.isbn = check_isbn(mi.isbn)
		self.log.info(mi)
		self.result_queue.put(mi)

	def parse_databazeknih_id(self, url):
		databazeknih_id_node = re.search('/knihy/(.*)', url).groups(0)[0]
		if databazeknih_id_node:
			return databazeknih_id_node
		else: return None
		
	def parse_first(self, root, xpath, loginfo, convert=lambda x: x[0].strip()):
		try:
			nodes = root.xpath(xpath)
			self.log.info('Found %s: %s' % (loginfo,nodes))
			return convert(nodes) if nodes else None
		except Exception as e:
			self.log.exception('Error parsing for %s with xpath: %s' % (loginfo, xpath))

	def parse_title(self, root):
		title_node = self.parse_first(root,'//h1[@itemprop="name"]/text()','title',lambda x: x[0].replace('&nbsp;','').strip())
		if title_node:
			return title_node
		else: return None
			
	def parse_series(self, root):
#		series_node = root.xpath('//div[@id="main"]//div[@id="content"]/div/div[4]/h3/a/text()')
#		series_node = root.xpath('//a[@class="strong"]/text()')
        series_node = root.xpath('//h3/a/text()')
		if series_node:
			self.log.info('series_node: %s'%series_node)
            series_index = root.xpath('//h3/em[@class="info"]/text()')
            if series_index:
				self.log.info('index_text: %s'%series_index)
				index = re.search('\((\d*)\.\)', series_index[0]).groups(0)[0]
				self.log.info('index: %s'%index)
				try:
					index = float(index)
				except:
					index = None
				self.log.info('index: %s'%index)
				return (series_node[0], index)
		else: return (None, None)
		
	def parse_authors(self, root):
		author_nodes = root.xpath('//h2[@class="jmenaautoru"]/a/text()')
		if author_nodes:
			authors = []
			self.log.info('eee %s'%author_nodes[0])
			acko = u''.join(author_nodes[0])
			authors.append(acko)
			return authors
		else: return None

	def parse_tags(self, root):
		ret_nodes = root.xpath('//h5[@itemprop="category"]/a/text()')
		if ret_nodes:
			tags = []
			self.log.info('ttt %s'%ret_nodes[0])
			for node in ret_nodes: 
				tcko = u''.join(node)
				tags.append(tcko)
			return tags
		else: return None

	def parse_pubdate(self, root):
		txt_more = root.xpath('//span[@itemprop="datePublished"]/text()')
		if txt_more:
			year = int(txt_more[0])
			month = 1
			day = 1
			from calibre.utils.date import utc_tz
			pubdate = datetime(year, month, day, tzinfo=utc_tz)
			return pubdate
		else: return None
		
	def parse_comments(self, root):
		description_node = root.xpath('//p[@id="biall"]/text()')
		self.log.info('comm_node: %s'%description_node)
		if description_node:
			return ''.join(description_node)
		else:
#			description_node = root.xpath('//p[@class="justify odtop_ten oddown"]/text()')
			description_node = root.xpath('//p[@itemprop="description"]/text()')
			self.log.info('comm_node: %s'%description_node)
			if description_node:
				return ''.join(description_node)
			else: return None

	
	def parse_isbn(self, root):
#		return '00'
#		txt_node = root.xpath('//span[@itemprop="identifier"]/text()')
        try:
		    txt_node = root.xpath('//a[@id="bukinfo"]/@bid')
            urlISBN = 'http://www.databazeknih.cz/helpful/ajax/more_binfo.php?bid=' + str(txt_node[0])
		except:
            return None
		self.log.info('More info: %s'%urlISBN)
		raw = self.browser.open_novisit(urlISBN, timeout=self.timeout)#.read().strip()
		root = lh.parse(raw)
        txt_more = root.xpath('//span[@itemprop="isbn"]/text()')
		if txt_more:
			self.log.info('ISBN : %s'%txt_more[0])
			ret_node = txt_more[0]
			if ret_node:
				return ret_node
			else: return txt_node[0]
		else: return txt_node[0]

	def parse_publisher(self, root):
        publisher_nodes = root.xpath('//span[@itemprop="publisher"]/a/text()')
        self.log.info('Publisher %s'%publisher_nodes[0])
        if publisher_nodes:
            self.log.info('Publisher %s'%publisher_nodes[0])
            return publisher_nodes[0]
        else: return None
		
	def parse_rating(self, root):
		rating_node = root.xpath('//a[@class="bpoints"]/text()')
		self.log.info('Rating_node: %s'%rating_node)
#		self.log.info('LEN Rating_node: %s'%len(rating_node))
		if len(rating_node) > 0:
			rating_node = rating_node[0].strip("%")
		else: rating_node = '0'
		rating_node = float(rating_node)
#		rating_node = round(rating_node * 0.05)
		self.log.info('Rating_num: %s'%rating_node)
		if rating_node:
			if rating_node >= 90:
				out_rating = 5
			elif rating_node >= 70:
				out_rating = 4
			elif rating_node >= 50:
				out_rating = 3
			elif rating_node >= 30:
				out_rating = 2
			elif rating_node >= 10:
				out_rating = 1
			else:
				out_rating = 0
			return out_rating
		else: return None
	
	def parse_cover(self, root):
		book_cover = root.xpath('//img[@class="kniha_img"]/@src')
		imgcol_node = book_cover
		self.log.info('Cover: %s'%imgcol_node)
		if imgcol_node:
			adr_img = imgcol_node[0]
            imgcol_node_big=imgcol_node[0].replace("mid_","big_",1);
			if adr_img[:7] != 'http://':
				imgcol_node_big = 'http://www.databazeknih.cz/'+imgcol_node_big
			return imgcol_node_big
		else: return None

