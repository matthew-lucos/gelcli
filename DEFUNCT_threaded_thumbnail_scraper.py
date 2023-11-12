#	Does not work.
#	May try to implement again sometime.

from gelbooru_scraper.py import *
import requests
import bs4
import threading


def _thumbnail_scrape_worker(
	page_start_idx,
	page_end_idx,
	thumbnails,
	session,
	results_page_url, 
	is_blank_page_reached, 
	lock
) -> None:
	
	resp = session.get(results_page_url)
	soup = bs4.BeautifulSoup(resp.text, features='lxml')
	thumbnails_list: list[bs4.Tag] = \
		[img for img in soup.find_all('img') \
		if 'img3' in img['src']]
		
	if len(thumbnails_list) == 0:
		with lock:
			is_blank_page_reached[0] = True
		return
	
	with lock:
		for th in thumbnails_list[:page_end_idx + 1]:			
			thumbnails.add(th)


def threaded_get_image_thumbnails(tags=None, page_start_num=0, end_num=-1, max_threads=30) -> set[bs4.Tag]:
	'''
	PROBLEM:
	for large requests (~16,000 as per test), 
	not all thumbnails are put in the thumbnails list by the threads 
	'''
	if tags is None:
		tags = []
	session = requests.Session()
	lock = threading.Lock()
	thumbnails: set[bs4.Tag] = set()
	is_blank_page_reached: list[bool] = [False]
	
	threads: list[threading.Thread] = []
	
	while is_blank_page_reached[0] is False:		
		if threading.active_count() >= max_threads:
			continue
		
		results_page_url = \
			BASE_SEARCH_URL \
			+ f'&tags={_stringify_tags(tags)}' \
			+ f'&pid={page_start_num}'
		
		if (end_num == -1) or (end_num - page_start_num > 41):
			t = threading.Thread(
				target=_thumbnail_scrape_worker,
				args=(
					0, 41, thumbnails, 
					session, results_page_url,
					is_blank_page_reached, lock
				),
				daemon=True
			)
			threads.append(t)
			t.start()
			page_start_num += 41
		else:
			t = threading.Thread(
				target=_thumbnail_scrape_worker,
				args=(
					0, (end_num - page_start_num), thumbnails, 
					session, results_page_url,
					is_blank_page_reached, lock
				),
				daemon=True
			)
			threads.append(t)
			t.start()
			break
	
	for t in threads:
		t.join()

	return thumbnails


