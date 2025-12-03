import requests
import time
import random
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sys
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('iot_simulation.log')
    ]
)

# Configuration for Render deployment
BASE_URL = 'https://traffic-backend-97ga.onrender.com/api/traffic-data'
LOCATIONS = {
    'Ikeja': {'lat': 6.5998, 'lon': 3.3460},
    'Victoria Island': {'lat': 6.4295, 'lon': 3.4236},
    'Surulere': {'lat': 6.5537, 'lon': 3.3660},
    'Lekki': {'lat': 6.4654, 'lon': 3.5660},
    'Apapa': {'lat': 6.4489, 'lon': 3.3590},
    'Marina': {'lat': 6.4434, 'lon': 3.4000},
    'Yaba': {'lat': 6.5095, 'lon': 3.3711},
    'Ikoyi': {'lat': 6.4522, 'lon': 3.4358},
}
INTERVAL = 30  # Seconds between updates
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # Base backoff multiplier

# Traffic patterns based on time of day (WAT - West Africa Time)
TRAFFIC_PATTERNS = {
    'early_morning': {'range': (5, 7), 'vehicles': (20, 60)},      # 5 AM - 7 AM
    'morning_peak': {'range': (7, 10), 'vehicles': (80, 200)},     # 7 AM - 10 AM
    'midday': {'range': (10, 13), 'vehicles': (40, 120)},          # 10 AM - 1 PM
    'afternoon_peak': {'range': (13, 16), 'vehicles': (70, 180)},  # 1 PM - 4 PM
    'evening': {'range': (16, 19), 'vehicles': (50, 140)},         # 4 PM - 7 PM
    'night': {'range': (19, 5), 'vehicles': (10, 50)}              # 7 PM - 5 AM
}

# Special events that can cause traffic spikes
SPECIAL_EVENTS = {
    'accident': {'probability': 0.05, 'multiplier': (2.0, 3.0)},
    'road_work': {'probability': 0.03, 'multiplier': (1.5, 2.0)},
    'event': {'probability': 0.02, 'multiplier': (1.8, 2.5)},
    'rain': {'probability': 0.08, 'multiplier': (1.3, 1.8)}
}

class TrafficSimulator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Traffic-IoT-Simulator/1.0'
        })
        self.stats = {
            'successful_requests': 0,
            'failed_requests': 0,
            'total_requests': 0,
            'last_success': None,
            'locations_sent': 0
        }
        self.running = True
        
    def get_current_traffic_pattern(self, hour: int) -> Tuple[int, int]:
        """Get vehicle range based on current time and traffic patterns."""
        for pattern_name, pattern in TRAFFIC_PATTERNS.items():
            start, end = pattern['range']
            if start < end:
                if start <= hour < end:
                    return pattern['vehicles']
            else:  # Overnight range (e.g., 19-5)
                if hour >= start or hour < end:
                    return pattern['vehicles']
        # Default to night pattern if no match found
        return TRAFFIC_PATTERNS['night']['vehicles']
    
    def check_special_events(self) -> float:
        """Check for special events that affect traffic."""
        multiplier = 1.0
        for event_name, event_config in SPECIAL_EVENTS.items():
            if random.random() < event_config['probability']:
                event_multiplier = random.uniform(*event_config['multiplier'])
                multiplier *= event_multiplier
                logging.info(f"Special event detected: {event_name} (multiplier: {event_multiplier:.2f})")
        return multiplier
    
    def generate_prediction(self, current_vehicles: int, hour: int) -> int:
        """Generate realistic traffic prediction for next 5 minutes."""
        # Base prediction on current traffic and time patterns
        base_prediction = current_vehicles
        
        # Add trend based on time of day
        if 6 <= hour < 9:  # Morning rush building up
            trend = random.randint(5, 20)
        elif 16 <= hour < 19:  # Evening rush building up
            trend = random.randint(5, 15)
        else:  # Stable or decreasing traffic
            trend = random.randint(-10, 10)
            
        prediction = max(10, base_prediction + trend)
        
        # Add some randomness but keep it realistic
        prediction_variation = random.randint(-15, 15)
        return max(10, prediction + prediction_variation)
    
    def get_vehicle_count(self, hour: int, location: str) -> Tuple[int, int]:
        """Generate realistic vehicle count and prediction."""
        # Get base traffic pattern
        min_vehicles, max_vehicles = self.get_current_traffic_pattern(hour)
        
        # Apply location-specific adjustments
        location_factors = {
            'Ikeja': 1.2,  # Typically busier
            'Victoria Island': 1.3,  # Business district
            'Lekki': 1.1,
            'Apapa': 1.4,  # Port area, often congested
            'Marina': 0.9,  # CBD but more organized
            'Surulere': 1.0,
            'Yaba': 1.1,
            'Ikoyi': 0.8   # Residential, less congested
        }
        
        location_factor = location_factors.get(location, 1.0)
        adjusted_min = int(min_vehicles * location_factor)
        adjusted_max = int(max_vehicles * location_factor)
        
        # Apply special events multiplier
        event_multiplier = self.check_special_events()
        final_min = int(adjusted_min * event_multiplier)
        final_max = int(adjusted_max * event_multiplier)
        
        # Generate current vehicle count
        current_vehicles = random.randint(final_min, final_max)
        
        # Generate prediction
        prediction = self.generate_prediction(current_vehicles, hour)
        
        return current_vehicles, prediction
    
    def send_traffic_data_for_location(self, location: str, data: Dict) -> bool:
        """Send traffic data for a specific location to the backend with retry logic."""
        retries = 0
        
        while retries < MAX_RETRIES and self.running:
            try:
                self.stats['total_requests'] += 1
                
                response = self.session.post(
                    BASE_URL, 
                    json=data, 
                    timeout=15,  # Increased timeout for Render deployment
                    headers={'X-Simulator-Id': 'iot-traffic-simulator'}
                )
                
                if response.status_code in (200, 201):
                    self.stats['successful_requests'] += 1
                    self.stats['last_success'] = datetime.utcnow()
                    
                    try:
                        response_data = response.json()
                        logging.info(f"✅ {location}: {data['vehicles']} vehicles "
                                   f"(Pred: {data.get('prediction', 'N/A')})")
                    except json.JSONDecodeError:
                        logging.info(f"✅ {location}: {data['vehicles']} vehicles")
                    
                    return True
                    
                else:
                    logging.warning(f"⚠️ {location}: HTTP {response.status_code} - {response.text}")
                    retries += 1
                    
            except requests.exceptions.Timeout:
                logging.warning(f"⏰ {location}: Timeout (attempt {retries + 1}/{MAX_RETRIES})")
                retries += 1
                
            except requests.exceptions.ConnectionError:
                logging.error(f"🔌 {location}: Connection error (attempt {retries + 1}/{MAX_RETRIES})")
                retries += 1
                
            except requests.exceptions.RequestException as e:
                logging.error(f"❌ {location}: Request error: {e} (attempt {retries + 1}/{MAX_RETRIES})")
                retries += 1
            
            # Exponential backoff before retry
            if retries < MAX_RETRIES and self.running:
                wait_time = RETRY_BACKOFF ** retries
                logging.info(f"🔄 {location}: Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        self.stats['failed_requests'] += 1
        logging.error(f"🚫 {location}: Failed after {MAX_RETRIES} attempts")
        return False
    
    def send_data_for_all_locations(self):
        """Send traffic data for ALL locations simultaneously."""
        current_time = datetime.utcnow()
        wat_hour = (current_time.hour + 1) % 24  # Convert to WAT (UTC+1)
        
        logging.info(f"🔄 Sending data for all {len(LOCATIONS)} locations at {current_time.strftime('%H:%M:%S')}...")
        
        threads = []
        successful_locations = 0
        
        for location_name, coords in LOCATIONS.items():
            # Generate traffic data for each location
            vehicles, prediction = self.get_vehicle_count(wat_hour, location_name)
            
            data = {
                'location': location_name,
                'vehicles': vehicles,
                'prediction': prediction,
                'latitude': coords['lat'],
                'longitude': coords['lon'],
                'timestamp': current_time.isoformat() + 'Z',
                'congestionLevel': 'High' if vehicles > 100 else 'Medium' if vehicles > 50 else 'Low'
            }
            
            # Create a thread for each location to send data concurrently
            thread = threading.Thread(
                target=self._send_location_data_thread,
                args=(location_name, data)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        self.stats['locations_sent'] = len(LOCATIONS)
        logging.info(f"📦 Batch completed: {len(LOCATIONS)} locations processed")
    
    def _send_location_data_thread(self, location: str, data: Dict):
        """Thread target function for sending location data."""
        success = self.send_traffic_data_for_location(location, data)
        if success:
            logging.debug(f"🎯 {location}: Data sent successfully")
    
    def print_stats(self):
        """Print current simulation statistics."""
        success_rate = (self.stats['successful_requests'] / self.stats['total_requests'] * 100) if self.stats['total_requests'] > 0 else 0
        logging.info(f"\n📊 Simulation Statistics:")
        logging.info(f"   Total Requests: {self.stats['total_requests']}")
        logging.info(f"   Successful: {self.stats['successful_requests']} ({success_rate:.1f}%)")
        logging.info(f"   Failed: {self.stats['failed_requests']}")
        logging.info(f"   Locations: {self.stats['locations_sent']}")
        if self.stats['last_success']:
            logging.info(f"   Last Success: {self.stats['last_success'].strftime('%H:%M:%S')}")
    
    def run_simulation(self):
        """Main simulation loop."""
        logging.info("🚦 Starting IoT Traffic Simulation...")
        logging.info(f"📍 Monitoring {len(LOCATIONS)} locations")
        logging.info(f"⏰ Update interval: {INTERVAL} seconds")
        logging.info(f"🌐 Backend URL: {BASE_URL}")
        logging.info("Press Ctrl+C to stop the simulation\n")
        
        batch_counter = 0
        
        try:
            while self.running:
                # Send data for ALL locations
                self.send_data_for_all_locations()
                batch_counter += 1
                
                # Print stats every 5 batches
                if batch_counter % 5 == 0:
                    self.print_stats()
                
                # Wait for next interval
                logging.info(f"⏳ Waiting {INTERVAL} seconds until next update...\n")
                for i in range(INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                
        except KeyboardInterrupt:
            logging.info("\n\n🛑 Simulation stopped by user")
            self.running = False
            
        except Exception as e:
            logging.error(f"💥 Unexpected error: {e}")
            
        finally:
            self.print_stats()
            logging.info("📝 Logs saved to iot_simulation.log")

def main():
    """Main entry point."""
    simulator = TrafficSimulator()
    simulator.run_simulation()

if __name__ == "__main__":
    main()