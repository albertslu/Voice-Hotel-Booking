import React, { useState } from 'react';
import axios from 'axios';
import './SignupForm.css';

interface SignupData {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  title: 'MR' | 'MRS' | 'MS';
  cardNumber: string;
  cardExpiry: string;
  cardHolderName: string;
  cardVendor: 'VI' | 'MC' | 'AX';
}

const SignupForm: React.FC = () => {
  const [formData, setFormData] = useState<SignupData>({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    title: 'MR',
    cardNumber: '',
    cardExpiry: '',
    cardHolderName: '',
    cardVendor: 'VI'
  });

  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://api.hotelbooking.buzz';

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const formatCardNumber = (value: string) => {
    // Remove all non-digits
    const digits = value.replace(/\D/g, '');
    // Add spaces every 4 digits
    return digits.replace(/(\d{4})(?=\d)/g, '$1 ');
  };

  const formatExpiry = (value: string) => {
    // Remove all non-digits
    const digits = value.replace(/\D/g, '');
    // Add slash after 2 digits (MM/YY format)
    if (digits.length >= 2) {
      return digits.substring(0, 2) + '/' + digits.substring(2, 4);
    }
    return digits;
  };

  const handleCardNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatCardNumber(e.target.value);
    setFormData(prev => ({
      ...prev,
      cardNumber: formatted
    }));
  };

  const handleExpiryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatExpiry(e.target.value);
    setFormData(prev => ({
      ...prev,
      cardExpiry: formatted
    }));
  };

  const validateForm = (): boolean => {
    if (!formData.firstName || !formData.lastName || !formData.email || !formData.phone) {
      setMessage('Please fill in all personal information fields');
      return false;
    }

    if (!formData.cardNumber || !formData.cardExpiry || !formData.cardHolderName) {
      setMessage('Please fill in all payment information fields');
      return false;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setMessage('Please enter a valid email address');
      return false;
    }

    // Basic phone validation
    const phoneRegex = /^\+?[\d\s\-\(\)]{10,}$/;
    if (!phoneRegex.test(formData.phone)) {
      setMessage('Please enter a valid phone number');
      return false;
    }

    // Card number validation (remove spaces for validation)
    const cardDigits = formData.cardNumber.replace(/\s/g, '');
    if (cardDigits.length < 13 || cardDigits.length > 19) {
      setMessage('Please enter a valid card number');
      return false;
    }

    // Expiry validation (MM/YY format)
    if (!/^\d{2}\/\d{2}$/.test(formData.cardExpiry)) {
      setMessage('Please enter expiry date in MM/YY format');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      setIsSuccess(false);
      return;
    }

    setIsLoading(true);
    setMessage('');

    try {
      // Step 1: Create user account
      const userPayload = {
        first_name: formData.firstName,
        last_name: formData.lastName,
        email: formData.email,
        phone: formData.phone,
        title: formData.title
      };

      const userResponse = await axios.post(`${API_BASE_URL}/users/signup`, userPayload);
      
      if (userResponse.status === 200) {
        // Step 2: Add payment method
        const paymentPayload = {
          email: formData.email,
          card_number: formData.cardNumber.replace(/\s/g, ''), // Remove spaces
          card_expiry: formData.cardExpiry.replace('/', '-'), // Convert MM/YY to MM-YY
          card_holder_name: formData.cardHolderName,
          card_vendor: formData.cardVendor
        };

        const paymentResponse = await axios.post(`${API_BASE_URL}/users/add-payment`, paymentPayload);
        
        if (paymentResponse.status === 200) {
          setMessage('Account created successfully! You can now book hotels by calling our voice assistant.');
          setIsSuccess(true);
          
          // Clear form
          setFormData({
            firstName: '',
            lastName: '',
            email: '',
            phone: '',
            title: 'MR',
            cardNumber: '',
            cardExpiry: '',
            cardHolderName: '',
            cardVendor: 'VI'
          });
        }
      }
    } catch (error: any) {
      console.error('Signup error:', error);
      
      if (error.response?.data?.detail) {
        setMessage(error.response.data.detail);
      } else if (error.response?.status === 400) {
        setMessage('Invalid information provided. Please check your details and try again.');
      } else {
        setMessage('Failed to create account. Please try again later.');
      }
      setIsSuccess(false);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="signup-container">
      <div className="signup-form">
        <h1>Sign Up for Voice Hotel Booking</h1>
        <p className="subtitle">Create your account to book hotels with our voice assistant</p>
        
        <form onSubmit={handleSubmit}>
          {/* Personal Information */}
          <div className="form-section">
            <h3>Personal Information</h3>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="title">Title</label>
                <select
                  id="title"
                  name="title"
                  value={formData.title}
                  onChange={handleInputChange}
                  required
                >
                  <option value="MR">Mr.</option>
                  <option value="MRS">Mrs.</option>
                  <option value="MS">Ms.</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="firstName">First Name</label>
                <input
                  type="text"
                  id="firstName"
                  name="firstName"
                  value={formData.firstName}
                  onChange={handleInputChange}
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="lastName">Last Name</label>
                <input
                  type="text"
                  id="lastName"
                  name="lastName"
                  value={formData.lastName}
                  onChange={handleInputChange}
                  required
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="email">Email Address</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  required
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="phone">Phone Number</label>
                <input
                  type="tel"
                  id="phone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleInputChange}
                  placeholder="+1 (555) 123-4567"
                  required
                />
              </div>
            </div>
          </div>

          {/* Payment Information */}
          <div className="form-section">
            <h3>Payment Information</h3>
            <p className="payment-note">Your payment information is encrypted and secure</p>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="cardHolderName">Cardholder Name</label>
                <input
                  type="text"
                  id="cardHolderName"
                  name="cardHolderName"
                  value={formData.cardHolderName}
                  onChange={handleInputChange}
                  required
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="cardNumber">Card Number</label>
                <input
                  type="text"
                  id="cardNumber"
                  name="cardNumber"
                  value={formData.cardNumber}
                  onChange={handleCardNumberChange}
                  placeholder="1234 5678 9012 3456"
                  maxLength={19}
                  required
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="cardExpiry">Expiry Date</label>
                <input
                  type="text"
                  id="cardExpiry"
                  name="cardExpiry"
                  value={formData.cardExpiry}
                  onChange={handleExpiryChange}
                  placeholder="MM/YY"
                  maxLength={5}
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="cardVendor">Card Type</label>
                <select
                  id="cardVendor"
                  name="cardVendor"
                  value={formData.cardVendor}
                  onChange={handleInputChange}
                  required
                >
                  <option value="VI">Visa</option>
                  <option value="MC">Mastercard</option>
                  <option value="AX">American Express</option>
                </select>
              </div>
            </div>
          </div>

          {message && (
            <div className={`message ${isSuccess ? 'success' : 'error'}`}>
              {message}
            </div>
          )}

          <button 
            type="submit" 
            className="submit-btn"
            disabled={isLoading}
          >
            {isLoading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <div className="voice-info">
          <h3>🎤 How to Book Hotels by Voice</h3>
          <p>After signing up, call our voice assistant:</p>
          <div className="phone-number">📞 +1 (555) HOTEL-1</div>
          <p>Just say: <em>"Book a hotel in [city] for [dates]"</em></p>
        </div>
      </div>
    </div>
  );
};

export default SignupForm;
