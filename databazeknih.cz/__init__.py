#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# *-* coding: utf-8 *-*
from __future__ import (unicode_literals, division, absolute_import,
						print_function)

__license__   = 'GPL v3'
__copyright__ = '2017, Frantisek Lorenc <franta.lorenc@gmail.com>'
__copyright__ = 'based od Pavel Skulil <pavelsku@gmail.com>'

__docformat__ = 'restructuredtext cs'

import time
from Queue import Queue, Empty
from lxml.html import fromstring
from calibre import as_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars
import lxml, sys, traceback, urllib, urllib2
from calibre import browser


class databazeknih(Source):
	name					= 'Databazeknih'
	description				= _('Downloads metadata and covers from databazeknih.cz')
	author					= 'vecdan based on bagdira version'
	version					= (1, 5, 0)
	minimum_calibre_version = (0, 8, 0)

	capabilities = frozenset(['identify', 'cover'])
	touched_fields = frozenset(['title', 'authors', 'identifier:databazeknih', 'tags', 'comments', 'rating', 'series', 'publisher','pubdate'])
	has_html_comments = False
	supports_gzip_transfer_encoding = False

	BASE_URL = "http://www.databazeknih.cz/"
	
	def config_widget(self):
		'''
		Overriding the default configuration screen for our own custom configuration
		'''
		from calibre_plugins.databazeknih.config import ConfigWidget
		return ConfigWidget(self)
		
	def get_book_url(self, identifiers):
		databazeknih_id = identifiers.get('databazeknih', None)
		if databazeknih_id:
			return (self.name, databazeknih_id,
					databazeknih.BASE_URL + 'knihy/' + databazeknih_id)

	def create_query(self, log, title=None, authors=None):
		if title is not None:
			search_title = title.replace(' ', '+')
		else:
			search_title = ' '
			
		if authors is not None:
			search_author = authors[0].replace(' ', '+')
		else:
			search_author = ' '

#		search_page = 'http://moly.hu/kereses?q=%s+%s&x=0&y=0'%(search_author, search_title)
		SP = 'http://www.databazeknih.cz/index.php?stranka=search&q={title}'
		search_page = SP.format(title=urllib2.quote(search_title.encode('utf-8')))
		return search_page

	def get_cached_cover_url(self, identifiers):
		url = None
		databazeknih_id = identifiers.get(u'databazeknih', None)
		if databazeknih_id is None:
			isbn = check_isbn(identifiers.get(u'isbn', None))
			if isbn is not None:
				databazeknih_id = self.cached_isbn_to_identifier(isbn)
		if databazeknih_id is not None:
			url = self.cached_identifier_to_cover_url(databazeknih_id)
			return url

	def identify(self, log, result_queue, abort, title, authors,
			identifiers={}, timeout=30):
		'''
		Note this method will retry without identifiers automatically if no
		match is found with identifiers.
		'''
		matches = []
		databazeknih_id = identifiers.get('databazeknih', None)
		log.info(u'\nTitl1e:%s\nAuthors:%s\n'%(title, authors))
		br = browser()
		if databazeknih_id:
			matches.append(databazeknih.BASE_URL + 'knihy/' + databazeknih_id)
		else:
			query = self.create_query(log, title=title, authors=authors)
			if query is None:
				log.error('Insufficient metadata to construct query')
				return
			try:
				log.info(u'Querying: %s'%query)
			
				response = br.open(query)
			except Exception as e:
				isbn = check_isbn(identifiers.get('isbn', None))
				if isbn and callable(getattr(e, 'getcode', None)) and e.getcode() == 404:
					log.info('Failed to find match for ISBN: %s'%isbn)
				else:
					err = 'Failed to make identify query: %r'%query
					log.info(err)
					return as_unicode(e)
#					return e
			try:
				raw = response.read().strip()
				raw = raw.decode('utf-8', errors='replace')
				if not raw:
					log.error('Failed to get raw result for query: %r'%query)
					return
				root = fromstring(clean_ascii_chars(raw))
			except:
				msg = 'Failed to parse databazeknih page for query: %r'%query
				log.exception(msg)
				return msg
			
			self._parse_search_results(log, title, authors, root, matches, timeout)

		if abort.is_set():
			return
		
		if not matches:
			if identifiers and title and authors:
				log.info('No matches found with identifiers, retrying using only'
						' title and authors')
				return self.identify(log, result_queue, abort, title=title,
						authors=authors, timeout=timeout)
			log.error('No matches found with query: %r'%query)
			return
			
		log.debug('Starting workers for: %s' % (matches,))	
		from calibre_plugins.databazeknih.worker import Worker
		workers = [Worker(url, result_queue, br, log, i, self) for i, url in
				enumerate(matches)]

		for w in workers:
			w.start()
			time.sleep(0.1)

		while not abort.is_set():
			a_worker_is_alive = False
			for w in workers:
				w.join(0.2)
				if abort.is_set():
					break
				if w.is_alive():
					a_worker_is_alive = True
			if not a_worker_is_alive:
				break

		return None
	def _parse_search_results(self, log, orig_title, orig_authors, root, matches, timeout):
		log.info('Parse')
		results = root.xpath('//*[@class="new_search"]')
		results.sort()
		import calibre_plugins.databazeknih.config as cfg
#		max_results = cfg.plugin_prefs[cfg.STORE_NAME][cfg.KEY_MAX_DOWNLOADS]
		max_results = 10
		i = 0
		for result in results:
            title = results[i].xpath('a//text()')
			log.info('kniha: %s'%title)
			log.info('orig.autor: %s'%orig_authors)
			product = results[i].xpath('span[@class="smallfind"]//text()')
			product = product[0]
			product = product.split()
			prijmeni = product[len(product)-1]
			if prijmeni == '(pseudonym)':
				prijmeni = product[len(product)-2]
			log.info('produkt:%s<<'%prijmeni)
			vlozit = False
#			log.info('data %s'%data)
# ***************************************************
            if orig_authors:
                for o_jmena in orig_authors:
				    log.info('ojmena: %s'%o_jmena)
    				os_jmena = o_jmena.lower().split()
	    			log.info('osjmena0 :%s<<'%os_jmena[0])
		    		#log.info('osjmena1 :%s<<'%os_jmena[1])
			    	if prijmeni.lower() in os_jmena:
				    	log.info('ano')
					    vlozit=True
			book_url = results[i].xpath('a/@href')
			log.info('Book URL:%r'%book_url)
			result_url = 'http://www.databazeknih.cz/' + book_url[0]
			log.info('Result URL:%r'%result_url)
			i = i+1
			if vlozit:
				matches.append(result_url)
			if len(matches) >= max_results:
				break
	def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
		cached_url = self.get_cached_cover_url(identifiers)
		if cached_url is None:
			log.info('No cached cover found, running identify')
			rq = Queue()
			self.identify(log, rq, abort, title=title, authors=authors, identifiers=identifiers)
			if abort.is_set():
				return
			results = []
			while True:
				try:
					results.append(rq.get_nowait())
				except Empty:
					break
			results.sort(key=self.identify_results_keygen(
				title=title, authors=authors, identifiers=identifiers))
			for mi in results:
				cached_url = self.get_cached_cover_url(mi.identifiers)
				if cached_url is not None:
					break
		if cached_url is None:
			log.info('No cover found')
			return

		if abort.is_set():
			return
		br = self.browser
		log.info('Downloading cover from:', cached_url)
		try:
			cdata = br.open_novisit(cached_url, timeout=timeout).read()
			result_queue.put((self, cdata))
		except:
			log.exception('Failed to download cover from:', cached_url)
