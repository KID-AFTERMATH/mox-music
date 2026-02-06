import stripe
import os
from dotenv import load_dotenv

load_dotenv()

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        
    def create_payment_link(self, amount, song_title, promotion_tier):
        """Create Stripe payment link for song promotion"""
        try:
            product = stripe.Product.create(
                name=f"Song Promotion: {song_title}",
                description=f"{promotion_tier} promotion package"
            )
            
            price = stripe.Price.create(
                unit_amount=amount * 100,  # Convert to cents
                currency="usd",
                product=product.id,
            )
            
            payment_link = stripe.PaymentLink.create(
                line_items=[{"price": price.id, "quantity": 1}],
                after_completion={
                    "type": "redirect",
                    "redirect": {
                        "url": os.getenv('SUCCESS_URL', 'http://localhost:8501/success')
                    }
                },
            )
            
            return payment_link.url
        except Exception as e:
            print(f"Payment error: {e}")
            return None
