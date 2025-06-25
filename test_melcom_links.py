import requests
from melcom_scraper import scrape_melcom

def test_melcom_links():
    """Test Melcom link generation with a simple query"""
    print("Testing Melcom link generation...")
    
    # Test with a simple query
    query = "rice cooker"
    results = scrape_melcom(query, max_results=3)
    
    print(f"\nFound {len(results)} results for '{query}':")
    
    for i, product in enumerate(results, 1):
        print(f"\nProduct {i}:")
        print(f"  Name: {product['name']}")
        print(f"  Price: {product['price']}")
        print(f"  Link: {product['link']}")
        
        # Test if the link is accessible
        try:
            response = requests.head(product['link'], timeout=10)
            print(f"  Link Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ Link works!")
            else:
                print(f"  ❌ Link returns status {response.status_code}")
        except Exception as e:
            print(f"  ❌ Link error: {e}")

    # Test the updated Melcom scraper
    print("Testing Melcom link generation...")
    results = scrape_melcom("laptop", 3)  # Test with a different product

if __name__ == "__main__":
    test_melcom_links() 