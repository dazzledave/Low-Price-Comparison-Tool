import requests
from bs4 import BeautifulSoup

def scrape_tonaton(query):
    base_url = "https://tonaton.com/en/ads/ghana"
    search_url = f"{base_url}?q={query.replace(' ', '+')}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []
    listings = soup.select('li.listing-card')

    for item in listings[:5]:  # Limit to top 5 results
        title_tag = item.select_one('h2.title')
        price_tag = item.select_one('div.price')
        link_tag = item.select_one('a')

        if title_tag and price_tag and link_tag:
            title = title_tag.get_text(strip=True)
            price = price_tag.get_text(strip=True)
            url = "https://tonaton.com" + link_tag['href']
            results.append({
                'title': title,
                'price': price,
                'url': url
            })

    return results
