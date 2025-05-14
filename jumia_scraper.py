import requests
from bs4 import BeautifulSoup

def scrape_jumia(query, max_results=5):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    }
    
    search_url = f"https://www.jumia.com.gh/catalog/?q={query.replace(' ', '+')}"
    response = requests.get(search_url, headers=headers)

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    products = soup.select('article.prd')

    results = []
    for product in products:
        name_tag = product.select_one('h3.name')
        price_tag = product.select_one('div.prc')
        link_tag = product.find('a', href=True)
        image_tag = product.select_one('img')

        if name_tag and price_tag and link_tag:
            name = name_tag.get_text(strip=True)
            price = price_tag.get_text(strip=True)
            link = 'https://www.jumia.com.gh' + link_tag['href'].split('?')[0]
            image = image_tag['data-src'] if image_tag and image_tag.has_attr('data-src') else ''

            results.append({
                'name': name,
                'price': price,
                'link': link,
                'image': image
            })

            if len(results) >= max_results:
                break

    return results
