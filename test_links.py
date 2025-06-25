from jumia_scraper import scrape_jumia
from melcom_scraper import scrape_melcom
import requests

print("Testing product links...")
print("=" * 50)

# Test Jumia links
print("JUMIA LINKS:")
jumia_results = scrape_jumia('microwave', 2)
for i, product in enumerate(jumia_results, 1):
    print(f"{i}. {product['name']}")
    print(f"   Price: {product['price']}")
    print(f"   Link: {product['link']}")
    
    # Test if link is accessible
    try:
        response = requests.head(product['link'], timeout=5, allow_redirects=True)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Link works!")
        else:
            print(f"   ❌ Link returns {response.status_code}")
    except Exception as e:
        print(f"   ❌ Link error: {e}")
    print()

print("=" * 50)

# Test Melcom links
print("MELCOM LINKS:")
melcom_results = scrape_melcom('microwave', 2)
for i, product in enumerate(melcom_results, 1):
    print(f"{i}. {product['name']}")
    print(f"   Price: {product['price']}")
    print(f"   Link: {product['link']}")
    
    # Test if link is accessible
    try:
        response = requests.head(product['link'], timeout=5, allow_redirects=True)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Link works!")
        else:
            print(f"   ❌ Link returns {response.status_code}")
    except Exception as e:
        print(f"   ❌ Link error: {e}")
    print() 