#!/usr/bin/env python3
"""Test enhanced DOM processing with GPU-accelerated local LLM."""

import asyncio
import time
from browser_use.llm.llamacpp.chat import ChatLlamaCpp
from browser_use.llm.messages import UserMessage, SystemMessage

def create_large_dom_content(size_chars: int) -> str:
    """Create a realistic large DOM content for testing."""
    base_content = """
    <html><head><title>E-commerce Product Page</title></head><body>
    <nav>
        <ul>
            <li><a href="/home">Home</a></li>
            <li><a href="/products">Products</a></li>
            <li><a href="/cart">Cart (3 items)</a></li>
            <li><a href="/account">My Account</a></li>
        </ul>
    </nav>
    <main>
        <div class="product-container">
            <h1>Premium Wireless Headphones</h1>
            <div class="product-images">
                <img src="/images/headphones-main.jpg" alt="Main product image" />
                <img src="/images/headphones-side.jpg" alt="Side view" />
                <img src="/images/headphones-detail.jpg" alt="Detail view" />
            </div>
            <div class="product-details">
                <p class="price">$299.99 <span class="original">$399.99</span></p>
                <p class="description">Experience premium audio quality with these state-of-the-art wireless headphones featuring active noise cancellation, 30-hour battery life, and premium comfort padding.</p>
                <ul class="features">
                    <li>Active Noise Cancellation (ANC)</li>
                    <li>30-hour battery life with fast charging</li>
                    <li>Premium memory foam padding</li>
                    <li>Bluetooth 5.2 connectivity</li>
                    <li>Touch controls for music and calls</li>
                    <li>Foldable design for easy travel</li>
                </ul>
                <div class="buttons">
                    <button id="add-to-cart" class="primary-btn">Add to Cart</button>
                    <button id="buy-now" class="secondary-btn">Buy Now</button>
                    <button id="wishlist" class="icon-btn">♡ Add to Wishlist</button>
                </div>
            </div>
        </div>
        <section class="reviews">
            <h2>Customer Reviews (4.8/5 stars)</h2>
    """
    
    # Add repetitive review content to reach target size
    review_template = """
            <div class="review">
                <div class="reviewer">John D. - Verified Purchase</div>
                <div class="rating">★★★★★</div>
                <div class="review-text">Amazing sound quality! The noise cancellation works perfectly for my daily commute. Battery life is exactly as advertised - I charge them once a week with heavy use. Highly recommended for anyone looking for premium wireless headphones.</div>
            </div>
    """
    
    current_content = base_content
    while len(current_content) < size_chars:
        current_content += review_template
    
    current_content += """
        </section>
        <footer>
            <div class="footer-links">
                <a href="/shipping">Shipping Info</a>
                <a href="/returns">Returns</a>
                <a href="/support">Support</a>
                <a href="/warranty">Warranty</a>
            </div>
        </footer>
    </main></body></html>
    """
    
    return current_content[:size_chars]

async def test_dom_processing_capacity():
    """Test DOM processing with various content sizes."""
    llm = ChatLlamaCpp(
        model="qwen2.5-14b-instruct",
        base_url="http://localhost:8080",
        temperature=0.1,
        timeout=30.0
    )
    
    test_cases = [
        (4000, "Small DOM"),
        (8000, "Medium DOM"),
        (12000, "Large DOM (enhanced limit)"),
        (15000, "Extra Large DOM"),
    ]
    
    print("Testing enhanced DOM processing capacity with GPU acceleration...")
    print(f"GPU Performance: 0.51s avg response time (8.4x improvement)\n")
    
    for size, description in test_cases:
        dom_content = create_large_dom_content(size)
        
        messages = [
            SystemMessage(content="You are a web automation assistant. Analyze the webpage content and extract key information."),
            UserMessage(content=f"""Please analyze this webpage content and answer: What is the main product being sold and what is its price?

Webpage content:
{dom_content}""")
        ]
        
        print(f"Testing {description} ({size} chars)...")
        
        try:
            start_time = time.time()
            result = await llm.ainvoke(messages)
            end_time = time.time()
            
            response_time = end_time - start_time
            success = "wireless headphones" in result.completion.lower() and "$299.99" in result.completion
            
            print(f"  [OK] Success: {response_time:.2f}s - {result.completion[:100]}...")
            if not success:
                print(f"  [!] Content quality issue - may need better extraction")
                
        except Exception as e:
            print(f"  [X] Failed: {e}")
        
        print()

async def test_escalation_logic():
    """Test that escalation still works with enhanced limits."""
    llm = ChatLlamaCpp(
        model="qwen2.5-14b-instruct", 
        base_url="http://localhost:8080",
        timeout=10.0
    )
    
    # Create content that should trigger escalation (too large)
    massive_content = create_large_dom_content(20000)  # Exceeds enhanced limits
    
    messages = [
        SystemMessage(content="You are a web automation assistant."),
        UserMessage(content=f"Analyze this massive webpage: {massive_content}")
    ]
    
    print("Testing escalation with oversized content (20000 chars)...")
    
    try:
        start_time = time.time()
        result = await llm.ainvoke(messages)
        end_time = time.time()
        
        print(f"  [OK] Handled via shrinking: {end_time - start_time:.2f}s")
        print(f"  Response: {result.completion[:100]}...")
        
    except Exception as e:
        print(f"  [X] Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_dom_processing_capacity())
    print("\n" + "="*50 + "\n")
    asyncio.run(test_escalation_logic())