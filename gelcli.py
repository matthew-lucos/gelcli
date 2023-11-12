#!/usr/bin/python3.8

import os
import shutil
import requests
import bs4
import threading
import queue
import argparse


BASE_SEARCH_URL = 'https://gelbooru.com/index.php?page=post&s=list'


def _stringify_tags(tags):
	return '+'.join(tags).replace(':', '%3a')


def _download_worker(scrape_queue, dir_path, session):
	while not scrape_queue.empty():
		download_image_from_post(
			scrape_queue.get(),
			dir_path,
			session
		)
		scrape_queue.task_done()


# API for scraping gelbooru

def get_image_thumbnails(tags, page_start_num, end_num):
	'''
	warning:

	some tags are uploaded to so frequently (e.g. rating:general)
	that when another request for a PAGE is made (using &pid=),
	the previously scraped images on the page have already
	shifted to the right in position 
	since the last time a PAGE was requested,
	causing some images in the downloads folder
	to be written to MORE THAN ONCE, resulting in 
	less than the expected amount of images scraped
	'''
	session = requests.Session()
	page_start_idx = page_start_num
	thumbnails = []	
	while True:	
		resp = session.get(
			BASE_SEARCH_URL 
			+ f'&tags={_stringify_tags(tags)}'
			+ '+-video' # exclude videos from results
			+ f'&pid={page_start_idx}'
		)
		soup = bs4.BeautifulSoup(resp.text, features='lxml')
		thumbnails_on_page = \
			[img for img in soup.find_all('img') if 'img3' in img['src']]
		# break if blank page
		if len(thumbnails_on_page) == 0:
				break
		if end_num == -1:
			thumbnails += thumbnails_on_page
		else:
			expected_length = end_num - page_start_num + 1
			thumbnails += thumbnails_on_page[:expected_length]
			if len(thumbnails) == expected_length:
				break
		# break if length of thumbnails has not changed from last iteration
		# i.e. blank page reached, ends
		if page_start_idx == len(thumbnails):
			break
		page_start_idx = len(thumbnails)
	return thumbnails


def download_image_from_post(url, dir_path, session=None):
	if dir_path[-1] in ('/', '\\'):
		dir_path = dir_path [:-1]
	if session is None:
		resp = requests.get(url)
	else:
		resp = session.get(url)
	soup = bs4.BeautifulSoup(resp.text, features='lxml')
	img = soup.find('img', {'id': 'image'})
	if img is None:
		print(f'Could not download media from {url} .')
		return
	if session is None:
		img_resp = requests.get(img['src'], stream=True)
	else:
		img_resp = session.get(img['src'], stream=True)
	with open(dir_path + '/' + img['src'].split('/')[-1], 'wb') as f:
		shutil.copyfileobj(img_resp.raw, f)


def download_images(**kw):
	tags = kw['tags'] if 'tags' in kw else []
	dir_path = kw['dir_path'] if 'dir_path' in kw else 'downloads_gelcli/'
	quantity = kw['quantity'] if 'quantity' in kw else 1
	start = kw['start'] if 'start' in kw else 0
	max_threads = kw['max_threads'] if 'max_threads' in kw else 10
	session = requests.Session()
	end_num = -1 if (quantity == -1) else (start + quantity - 1)
	thumbnails = get_image_thumbnails(tags, start, end_num)
	q = queue.Queue()
	for img in thumbnails:
		q.put(img.parent['href'])
	threads = []
	for _ in range(max_threads):
		threads.append(
			threading.Thread(
				target=_download_worker,
				args=(q, dir_path, session),
				daemon=True
			)
		)
	for t in threads:
		t.start()
	for t in threads:
		t.join()


def main():
	if not os.path.exists('downloads_gelcli/'):
		os.mkdir('downloads_gelcli')
	if not os.path.exists('default_dldir_path.txt'):
		with open('default_dldir_path.txt', 'w') as f:
			f.write('downloads_gelcli')
	parser = argparse.ArgumentParser()
	parser._action_groups.pop() # remove "optional arguments" category from -h print
	dpconfig_args = parser.add_argument_group(
		title='download path config args',
		description='[?] Used to view and configure the default download path before using the tool.'
	)
	settings_args = parser.add_argument_group(
		title='settings args',
		description='[?] Determine the scraper\'s arguments.'
	)
	usage_args = parser.add_argument_group(
		title='usage args',
		description='[?] Must be provided to start the scraper.'
	)
	# set new default download path
	dpconfig_args.add_argument(
		'-sp',
		type=str,
		help='set the default download path',
	)
	# view default download path
	dpconfig_args.add_argument(
		'-vp',
		help='print out the default download path',
		action='store_true'
	)
	# start
	settings_args.add_argument(
		'-s',
		type=int,
		help='nth image to start with',
	)
	# download folder path
	settings_args.add_argument(
		'-d',
		type=str,
		help='specify a different dir to download images to for this time',
	)
	# max. threads
	settings_args.add_argument(
		'-m',
		type=int,
		help='max. threads to run at once. (default 10)',
	)
	# quantity
	usage_args.add_argument(
		'-q',
		type=int,
		help='quantity of images to download. Use -1 if all (BE CAREFUL USING THIS!)',
	)
	# tags
	usage_args.add_argument(
		'-t',
		type=list,
		help='spaced string of tags that images should match. (e.g.) outdoors rating:general grass',
		nargs='+',
	)
	args = parser.parse_args()
	if (not args.q or not args.t) and (not args.sp and not args.vp):
		print('[*] The args -q and -t must be defined for a download to start.')
	start_num = args.s if args.s else 0
	max_threads = args.m if args.m else 10
	with open('default_dldir_path.txt', 'r') as f:
		dldir = args.d if args.d else f.read()
	if args.t and args.q:
		# args.t is a list of lists of strings
		tags = [''.join(tag) for tag in args.t] 
		download_images(
			tags=tags,
			dir_path=dldir,
			quantity=args.q,
			start=start_num,
			max_threads=max_threads
		)
		print(f'Images have finshed downloading to "{dldir}" .')
	if args.sp:
		with open('default_dldir_path.txt', 'w') as f:
			f.write(args.sp)
	if args.vp:
		print(dldir)


if __name__ == '__main__':
	main()

