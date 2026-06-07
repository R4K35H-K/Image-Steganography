import cv2
import numpy as np

import hashlib

# Delimiter bytes: 255 254 (1111111111111110)
DELIMITER = bytes([255, 254])

def get_prng_seed(password):
    if not password:
        return None
    # Generate a stable 32-bit integer seed from the password
    hash_bytes = hashlib.sha256(password.encode('utf-8')).digest()
    return int.from_bytes(hash_bytes[:4], byteorder='little')

def calculate_capacity(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return 0
    max_bits = img.shape[0] * img.shape[1] * 3
    max_bytes = max_bits // 8
    return max_bytes - len(DELIMITER)

def encode_image(image_path, payload_bytes, output_path, password=None, progress_callback=None):
    img = cv2.imread(image_path)
    if img is None:
        return False, "Could not read the input image."
        
    if progress_callback: progress_callback(0.1)
    data_with_delimiter = payload_bytes + DELIMITER
    
    # Convert payload to numpy uint8 array
    byte_array = np.frombuffer(data_with_delimiter, dtype=np.uint8)
    
    # Unpack bytes into bits
    bits = np.unpackbits(byte_array)
    
    data_len = len(bits)
    max_bits = img.shape[0] * img.shape[1] * 3
    
    if data_len > max_bits:
        return False, f"Data is too large. Image capacity: {max_bits//8} bytes, Required: {data_len//8} bytes."
        
    flat_img = img.flatten()
    if progress_callback: progress_callback(0.4)
        
    if password:
        seed = get_prng_seed(password)
        rng = np.random.default_rng(seed)
        indices = rng.permutation(max_bits)
        # Replace scattered LSBs
        flat_img[indices[:data_len]] = (flat_img[indices[:data_len]] & 254) | bits
    else:
        # Replace sequential LSBs: clear the 0th bit and OR with the payload bits
        flat_img[:data_len] = (flat_img[:data_len] & 254) | bits
    
    if progress_callback: progress_callback(0.7)
        
    encoded_img = flat_img.reshape(img.shape)
    
    # Save the output image
    success = cv2.imwrite(output_path, encoded_img)
    if progress_callback: progress_callback(1.0)
        
    if success:
        return True, "Successfully encoded data."
    else:
        return False, "Failed to save the image. Make sure the output path is valid."

def decode_image(image_path, password=None, progress_callback=None):
    img = cv2.imread(image_path)
    if img is None:
        return None
        
    if progress_callback: progress_callback(0.2)
    flat_img = img.flatten()
    max_bits = img.shape[0] * img.shape[1] * 3
    
    if progress_callback: progress_callback(0.4)
    
    if password:
        seed = get_prng_seed(password)
        rng = np.random.default_rng(seed)
        indices = rng.permutation(max_bits)
        lsb = flat_img[indices] & 1
    else:
        lsb = flat_img & 1
        
    lsb = lsb[:(len(lsb) // 8) * 8]
    
    if progress_callback: progress_callback(0.6)
    packed_bytes = np.packbits(lsb).tobytes()
    
    if progress_callback: progress_callback(0.8)
    idx = packed_bytes.find(DELIMITER)
    
    if progress_callback: progress_callback(1.0)
    
    if idx != -1:
        return packed_bytes[:idx]
        
    return None
