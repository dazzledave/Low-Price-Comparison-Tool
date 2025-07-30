# Pic2Price - Ghanaian Price Comparison Tool 🛒

A comprehensive web application that helps you find the best prices for products across major Ghanaian e-commerce platforms and international stores. Features AI-powered image recognition, advanced search capabilities, price alerts, and wishlist management.

## ✨ Features

### 🔍 **Multi-Platform Search**
- **Local Stores**: Jumia, Melcom, CompuGhana
- **International**: Amazon
- **Real-time Scraping**: Live price comparison across all platforms
- **Currency Support**: GHS (Ghana Cedi) and USD (US Dollar)

### 🖼️ **AI-Powered Image Search**
- **CLIP Model**: Advanced image recognition using OpenAI's CLIP
- **InceptionV3**: Traditional image classification
- **Smart Matching**: Automatically identifies products from uploaded images
- **Confidence Scoring**: Shows recognition accuracy

### 🔎 **Advanced Search**
- **Text Search**: Search by product name with advanced filters
- **Price Range**: Filter by minimum and maximum price
- **Store Filter**: Search specific stores only
- **Sort Options**: Price (low/high), name, store
- **Category Filter**: Filter by product category
- **In-Stock Filter**: Show only available products
- **Results Per Store**: Customize number of results (5-20 per store)

### 💰 **Price Alerts System**
- **One-Click Alerts**: Create alerts directly from search results
- **Email Notifications**: Get notified when prices drop
- **Multi-Currency**: Support for GHS and USD alerts
- **Alert Management**: Activate, deactivate, and delete alerts
- **Background Monitoring**: Automated price checking every 6 hours
- **Individual Checking**: Check specific alert prices manually

### ❤️ **Wishlist Management**
- **Save Products**: Add products to wishlist from search results
- **Organized View**: Browse saved products with store information
- **Export Feature**: Download wishlist as CSV
- **Statistics**: Track total items and stores

### 📊 **Analytics Dashboard**
- **Search Statistics**: Track search patterns and popular queries
- **Price History**: Monitor price trends over time
- **Usage Analytics**: View system usage statistics
- **Export Data**: Download analytics reports

### 🎨 **User Experience**
- **Dark/Light Mode**: Comfortable viewing experience
- **Responsive Design**: Works on all devices
- **Progressive Loading**: Real-time search progress indicators
- **Error Handling**: Robust error management
- **Caching System**: Improved performance with intelligent caching

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+** (recommended: Python 3.9 or higher)
- **pip** (Python package manager)
- **Git** (for cloning the repository)
- **ScraperAPI Account** (for web scraping functionality)

### Required Services

#### **ScraperAPI Setup**
This application uses [ScraperAPI](https://www.scraperapi.com/) for reliable web scraping. You'll need:

1. **Sign up** for a free ScraperAPI account
2. **Get your API key** from the dashboard
3. **Add to environment variables** (see setup below)

**Why ScraperAPI?**
- Bypasses anti-bot measures on e-commerce sites
- Ensures reliable scraping across all supported stores
- Handles JavaScript rendering for dynamic content
- Provides consistent results for price comparison

### Installation

1. **Clone the repository**:
```bash
git clone [your-repository-url]
cd Low-Price-Comparison-Tool
```

2. **Create virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**:
```bash
# Create .env file
touch .env  # On Windows: echo. > .env
```

5. **Configure .env file**:
```bash
# Add your ScraperAPI key
echo "SCRAPER_API=your_scraperapi_key_here" >> .env

# Optional: Add email configuration for price alerts
echo "EMAIL_USER=your-email@gmail.com" >> .env
echo "EMAIL_PASSWORD=your-app-password" >> .env
```

6. **Set up email configuration** (optional for price alerts):
```bash
cp config.py.example config.py
# Edit config.py with your email settings
```

7. **Run the application**:
```bash
python mainapp.py
```

8. **Open your browser**:
```
http://localhost:5000
```

## 📖 How to Use

### 🔍 **Basic Search**
1. **Text Search**: Enter product name in the search bar
2. **Advanced Search**: Use the Advanced Search page for detailed filtering
3. **Image Search**: Upload a product image for AI-powered recognition

### 💰 **Price Alerts**
1. **Create Alert**: Click "Set Alert" on any product card
2. **Set Target Price**: Enter your desired price
3. **Email Setup**: Configure Gmail for email notifications (optional)
4. **Manage Alerts**: View and manage alerts from the Price Alerts page

### ❤️ **Wishlist**
1. **Add to Wishlist**: Click "Add to Wishlist" on product cards
2. **View Wishlist**: Access from the navigation menu
3. **Export**: Download your wishlist as CSV

### 📊 **Analytics**
- **View Dashboard**: Access analytics from the navigation menu
- **Track Usage**: Monitor search patterns and price trends
- **Export Reports**: Download analytics data

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```bash
# Required: ScraperAPI for web scraping
SCRAPER_API=your_scraperapi_key_here

# Optional: Email configuration for price alerts
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

### Email Setup for Price Alerts

1. **Enable 2FA** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. **Update config.py**:
```python
EMAIL_USER = 'your-email@gmail.com'
EMAIL_PASSWORD = 'your-app-password'
```

### Environment Variables

Create a `config.py` file with:
```python
# Email Configuration
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USER = 'your-email@gmail.com'
EMAIL_PASSWORD = 'your-app-password'
SENDER_NAME = 'Pic2Price Price Alerts'
EMAIL_SUBJECT_PREFIX = 'Price Alert:'

# Price Monitoring
PRICE_CHECK_INTERVAL_HOURS = 6
MAX_PRICE_CHECKS_PER_RUN = 10
DELAY_BETWEEN_CHECKS = 2
```

## 🛠️ Technical Architecture

### **Backend Technologies**
- **Flask**: Web framework
- **SQLite**: Database for alerts, wishlist, analytics
- **Threading**: Concurrent web scraping
- **Schedule**: Background price monitoring

### **AI/ML Components**
- **CLIP**: OpenAI's Contrastive Language-Image Pre-training
- **InceptionV3**: Google's image classification model
- **TensorFlow**: Deep learning framework
- **PyTorch**: Machine learning framework

### **Web Scraping**
- **BeautifulSoup4**: HTML parsing
- **Requests**: HTTP client
- **Cache Manager**: Intelligent caching system
- **Error Handling**: Robust timeout and retry mechanisms

### **Frontend**
- **HTML5/CSS3**: Modern responsive design
- **JavaScript**: Dynamic interactions
- **Font Awesome**: Icons
- **CSS Variables**: Theme support (dark/light mode)

## 📁 Project Structure

```
Low Price Comparison Tool/
├── mainapp.py              # Main Flask application
├── requirements.txt        # Python dependencies
├── config.py              # Configuration settings
├── README.md              # This file
├── .gitignore             # Git ignore patterns
├── Templates/             # HTML templates
│   ├── base.html          # Base template
│   ├── index.html         # Home page
│   ├── upload.html        # Image upload page
│   ├── advanced_search.html # Advanced search
│   ├── result.html        # Search results
│   ├── price_alerts.html  # Price alerts management
│   ├── wishlist.html      # Wishlist page
│   ├── analytics.html     # Analytics dashboard
│   └── about.html         # About page
├── Static/                # Static assets
│   ├── style.css          # Main stylesheet
│   ├── uploads/           # Uploaded images
│   └── p2p_logo.png      # Logo
├── scrapers/              # Web scrapers
│   ├── jumia_scraper.py  # Jumia scraper
│   ├── melcom_scraper.py # Melcom scraper
│   ├── compughana_scraper.py # CompuGhana scraper
│   └── amazon_scraper.py # Amazon scraper
├── utils/                 # Utility modules
│   ├── image_recognition.py # AI image recognition
│   ├── currency_utils.py  # Currency conversion
│   └── cache_manager.py   # Caching system
├── models/                # AI model files
├── search_cache/          # Search result cache
└── uploads/               # User uploaded images
```

## 🔧 Development

### **Running in Development Mode**
```bash
python mainapp.py
```

### **Database Management**
The application uses SQLite with the following tables:
- `feedback`: User feedback on image recognition
- `wishlist`: Saved products
- `price_alerts`: Price monitoring alerts
- `search_history`: Search analytics
- `price_history`: Price tracking data

### **Adding New Stores**
1. Create new scraper in `scrapers/` directory
2. Follow existing scraper pattern
3. Add to `mainapp.py` import and scraping functions
4. Update templates to include new store

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **OpenAI CLIP** for image recognition capabilities
- **BeautifulSoup** for web scraping functionality
- **Flask** for the web framework
- **Font Awesome** for icons

## 📞 Support

For issues, questions, or contributions:
- Create an issue on GitHub
- Check the documentation
- Review the code comments

---

**Made with ❤️ for Ghanaian shoppers**
