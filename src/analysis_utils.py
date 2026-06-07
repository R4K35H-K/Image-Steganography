import numpy as np
from PIL import Image
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def extract_lsb_plane(image_path):
    """
    Extracts the 0th bitplane of the image and amplifies it to 255.
    Returns a PIL Image object representing the LSB plane.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    
    # Extract the 0th bit and multiply by 255 (0 becomes 0, 1 becomes 255)
    lsb_arr = (arr & 1) * 255
    
    lsb_img = Image.fromarray(lsb_arr.astype(np.uint8))
    return lsb_img

def generate_histogram(image_path):
    """
    Generates a zoomed-in histogram around the most frequent pixel intensities.
    Sequential LSB modifies the 0th bit, pairing up frequencies.
    Returns a PIL Image containing the plotted histogram.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    
    fig, ax = plt.subplots(figsize=(6, 4))
    
    # Flatten across all channels
    data = arr.flatten()
    
    # Find the most frequent pixel value (mode) to center our histogram
    counts = np.bincount(data, minlength=256)
    peak_val = int(np.argmax(counts))
    
    # Center a 50-bin window around the peak, bounded by 0 and 255
    start_val = max(0, peak_val - 25)
    end_val = min(255, start_val + 50)
    if end_val - start_val < 50:
        start_val = max(0, end_val - 50)
        
    # Plot the histogram in this active range
    ax.hist(data, bins=range(start_val, end_val + 1), color='purple', alpha=0.7, edgecolor='black')
    
    ax.set_title(f"Histogram PoV Pairs (Range {start_val}-{end_val})")
    ax.set_xlabel("Pixel Intensity")
    ax.set_ylabel("Frequency")
    
    # Save the plot to a memory buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    
    return Image.open(buf)

def generate_chi_square_plot(image_path):
    """
    Performs a Chi-Square attack on the image to detect sequential LSB embedding.
    Calculates the probability of hidden data across chunks of the image.
    Returns a PIL Image containing the plotted graph.
    """
    from scipy.stats import chisquare
    
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    data = arr[:, :, 2].flatten() # Blue channel
    
    chunk_size = len(data) // 100
    if chunk_size == 0: chunk_size = 1
    
    probabilities = []
    
    for i in range(1, 101):
        chunk = data[:i*chunk_size]
        counts = np.bincount(chunk, minlength=256)
        
        expected = []
        observed = []
        for j in range(0, 256, 2):
            pov_sum = counts[j] + counts[j+1]
            if pov_sum > 0: # Only test pairs that actually occur
                # If data is completely random LSB, the pair frequencies should be equal
                expected.append(pov_sum / 2.0)
                expected.append(pov_sum / 2.0)
                observed.append(counts[j])
                observed.append(counts[j+1])
                
        if len(expected) == 0:
            probabilities.append(0)
            continue
            
        # Ignore warning for small expected frequencies just for the sake of visualization
        chi2, p = chisquare(f_obs=observed, f_exp=expected)
        
        # If p is close to 1, observed == expected (which means it IS embedded with random data)
        # If p is close to 0, observed != expected (natural image)
        probabilities.append(p)
        
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(range(1, 101), probabilities, color='red', linewidth=2)
    ax.fill_between(range(1, 101), probabilities, color='red', alpha=0.3)
    ax.set_title("Chi-Square Attack (Detection over Image)")
    ax.set_xlabel("Percentage of Image Analyzed (%)")
    ax.set_ylabel("Probability of Embedded Data")
    ax.set_ylim([-0.1, 1.1])
    ax.grid(True, linestyle='--', alpha=0.7)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    
    return Image.open(buf)

def calculate_metrics(cover_path, stego_path):
    from skimage.metrics import structural_similarity as ssim
    from skimage.metrics import mean_squared_error, peak_signal_noise_ratio
    
    cover_img = np.array(Image.open(cover_path).convert("RGB"))
    stego_img = np.array(Image.open(stego_path).convert("RGB"))
    
    mse = mean_squared_error(cover_img, stego_img)
    psnr = peak_signal_noise_ratio(cover_img, stego_img, data_range=255)
    s_val = ssim(cover_img, stego_img, data_range=255, channel_axis=2)
    
    return {"MSE": float(mse), "PSNR": float(psnr), "SSIM": float(s_val)}

def generate_error_mask(cover_path, stego_path):
    cover_img = np.array(Image.open(cover_path).convert("RGB"), dtype=np.int16)
    stego_img = np.array(Image.open(stego_path).convert("RGB"), dtype=np.int16)
    
    diff = np.abs(cover_img - stego_img)
    diff = np.clip(diff * 255, 0, 255).astype(np.uint8)
    
    return Image.fromarray(diff)

def estimate_rs_payload(image_path):
    img = Image.open(image_path).convert("RGB")
    arr = np.array(Image.open(image_path).convert("L"))
    
    flat = arr.flatten()
    if len(flat) % 2 != 0:
        flat = flat[:-1]
    
    pairs = flat.reshape(-1, 2).astype(np.int32)
    
    def f_diff(p):
        return np.abs(p[:, 0] - p[:, 1])
        
    def F1(p):
        res = p.copy()
        res[:, 1] ^= 1
        return res
        
    def F_1(p):
        res = p.copy()
        x = res[:, 1]
        x_new = np.where(x % 2 == 0, x - 1, x + 1)
        res[:, 1] = np.clip(x_new, 0, 255)
        return res
        
    f_orig = f_diff(pairs)
    
    F1_p = F1(pairs)
    f_F1 = f_diff(F1_p)
    Rm = np.sum(f_F1 > f_orig)
    Sm = np.sum(f_F1 < f_orig)
    
    F_1_p = F_1(pairs)
    f_F_1 = f_diff(F_1_p)
    R_m = np.sum(f_F_1 > f_orig)
    S_m = np.sum(f_F_1 < f_orig)
    
    flipped_pairs = pairs.copy()
    flipped_pairs[:, 0] ^= 1
    flipped_pairs[:, 1] ^= 1
    
    f_orig_flipped = f_diff(flipped_pairs)
    
    f_F1_flipped = f_diff(F1(flipped_pairs))
    Rm_flip = np.sum(f_F1_flipped > f_orig_flipped)
    Sm_flip = np.sum(f_F1_flipped < f_orig_flipped)
    
    f_F_1_flipped = f_diff(F_1(flipped_pairs))
    R_m_flip = np.sum(f_F_1_flipped > f_orig_flipped)
    S_m_flip = np.sum(f_F_1_flipped < f_orig_flipped)
    
    d0 = float(Rm - Sm)
    d_0 = float(R_m - S_m)
    d1 = float(Rm_flip - Sm_flip)
    d_1 = float(R_m_flip - S_m_flip)
    
    a = 2 * (d1 + d0)
    b = (d_0 - d_1 - d1 - 3 * d0)
    c = d0 - d_0
    
    if a == 0: return 0.0
        
    discriminant = b**2 - 4*a*c
    if discriminant < 0: return 0.0
        
    x1 = (-b + np.sqrt(discriminant)) / (2*a)
    x2 = (-b - np.sqrt(discriminant)) / (2*a)
    
    x = x1 if abs(x1) < abs(x2) else x2
    p = x / (x + 1)
    
    return max(0.0, min(100.0, p * 200.0))
