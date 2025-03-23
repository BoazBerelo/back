import requests
import ssl
import socket
from datetime import datetime, timezone
import json
import concurrent.futures
from queue import Queue
import time
from config import logger , Config
from DataManagement import update_domains
from elasticapm import traces , capture_span

def check_certificate(url):
    try:
        context = ssl.create_default_context()
        with socket.create_connection((url, 443), timeout=Config.SSL_TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=url) as ssock:
                cert = ssock.getpeercert()

        expiry_date_str = cert['notAfter']
        expiry_date = datetime.strptime(expiry_date_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        issuer = dict(x[0] for x in cert['issuer'])
        return ('valid', expiry_date.strftime("%Y-%m-%d %H:%M:%S"), issuer.get('commonName', 'unknown'))
    except Exception as e:
        return ('failed', 'unknown', 'unknown')

def check_url_mt(domains, username, apm_context):
    # Create request-specific queues
    request_urls_queue = Queue()
    request_analyzed_queue = Queue()
    
    # Add domains to THIS request's queue
    for domain in domains:
        if isinstance(domain, dict) and 'url' in domain:
            request_urls_queue.put(domain['url'])
        else:
            request_urls_queue.put(domain)
    
    expected_count = request_urls_queue.qsize()
    logger.info(f"Added {expected_count} domains to queue for {username}")
    
    max_workers = min(Config.MAX_WORKERS, len(domains) * 2)
    
    def check_url(apm_context):
        traces.execution_context.set_transaction(apm_context)
        while not request_urls_queue.empty():
            url = request_urls_queue.get()
            with capture_span(name=url, span_type="cpu"):
                result = {
                    'url': url, 
                    'status_code': 'FAILED', 
                    'ssl_status': 'unknown',
                    'expiration_date': 'unknown', 
                    'issuer': 'unknown'
                }
                try:
                    url = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                    
                    # Run SSL and HTTP checks concurrently
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                        ssl_future = executor.submit(check_certificate, url)
                        http_future = executor.submit(
                            requests.get, 
                            f'http://{url}', 
                            timeout=Config.HTTP_TIMEOUT
                        )
    
                        ssl_status, expiry_date, issuer_name = ssl_future.result(timeout=Config.SSL_TIMEOUT)
                        http_response = http_future.result(timeout=Config.HTTP_TIMEOUT)
    
                        if http_response.status_code == 200:
                            result.update({
                                'status_code': 'OK',
                                'ssl_status': ssl_status,
                                'expiration_date': expiry_date,
                                'issuer': issuer_name
                            })
                    
                    request_analyzed_queue.put(result)
                except Exception as e:
                    logger.error(f"Error checking {url}: {str(e)}")
                    request_analyzed_queue.put(result)
                finally:
                    request_urls_queue.task_done()

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for _ in range(max_workers):
            futures.append(executor.submit(check_url,apm_context))
        
        done, not_done = concurrent.futures.wait(
            futures, 
            timeout=Config.OVERALL_CHECK_TIMEOUT,
            return_when=concurrent.futures.ALL_COMPLETED
        )
        
        if not_done:
            logger.warning(f"{len(not_done)} threads did not complete")
    
    # Collect results from THIS request's analyzed queue
    while not request_analyzed_queue.empty():
        result = request_analyzed_queue.get()
        results.append(result)
        request_analyzed_queue.task_done()

    logger.info(f"Expected {expected_count} results, got {len(results)} for {username}")
    if len(results) < expected_count:
        logger.warning(f"Lost {expected_count - len(results)} checks for {username}")

    update_domains(results, username)
    return results

if __name__ == '__main__':
    urls = ['www.google.com', 'www.facebook.com', 'www.youtube.com']
    username = 'example_user'
    check_url_mt(urls, username)