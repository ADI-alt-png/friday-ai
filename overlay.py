import tkinter as tk
import queue
import time

root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.attributes("-transparentcolor", "black")
root.configure(bg='black')

WIDTH = 700
HEIGHT = 280
root.geometry(f"{WIDTH}x{HEIGHT}+1150+150")

canvas = tk.Canvas(root, bg="black", highlightthickness=0, bd=0)
canvas.pack(fill="both", expand=True)

# Queues and data structures
word_queue = queue.Queue()
current_line_words = []  # Current line being built
all_lines = []  # All completed lines

FONT = ("Segoe UI", 18)
LINE_SPACING = 8
MAX_WORDS_PER_LINE = 20  # 20 words per line
MAX_LINES = 6  # Maximum 6 lines total

# Timer for completing current line
completion_timer = None

def reset_completion_timer():
    """Reset timer to complete line after pause"""
    global completion_timer
    if completion_timer:
        root.after_cancel(completion_timer)
    completion_timer = root.after(500, complete_current_line)

def process_queue():
    """Process one word from the queue"""
    try:
        word = word_queue.get_nowait()
        add_word_to_line(word)
        reset_completion_timer()
    except queue.Empty:
        pass
    finally:
        root.after(50, process_queue)

def add_word_to_line(word):
    """Add word to current line, create new line when full"""
    global current_line_words, all_lines
    
    # Add word to current line
    current_line_words.append(word)
    
    # If line has 20 words, complete it
    if len(current_line_words) >= MAX_WORDS_PER_LINE:
        complete_current_line()
    
    # Redraw
    draw()

def complete_current_line():
    """Complete current line and add to all_lines"""
    global current_line_words, all_lines, completion_timer
    
    # Cancel timer
    if completion_timer:
        root.after_cancel(completion_timer)
        completion_timer = None
    
    # If there are words in current line, complete it
    if current_line_words:
        line_text = " ".join(current_line_words)
        all_lines.append(line_text)
        print(f"[LINE] Added: '{line_text[:40]}...' (Total lines: {len(all_lines)})")
        
        # Clear current line
        current_line_words = []
        
        # Check if box is full (6 lines)
        if len(all_lines) >= MAX_LINES:
            print(f"[CLEAR] Box full! Clearing all {len(all_lines)} lines")
            all_lines.clear()  # Clear all lines
        
        # Redraw
        draw()

def draw():
    """Draw all lines"""
    canvas.delete("all")
    x, y = 25, 35
    
    # Draw all completed lines
    for line in all_lines:
        draw_text(x, y, line)
        
        # Calculate line height
        item = canvas.create_text(x, y, text=line, font=FONT, anchor="nw", width=WIDTH-50)
        bbox = canvas.bbox(item)
        canvas.delete(item)
        if bbox:
            y += (bbox[3] - bbox[1]) + LINE_SPACING
    
    # Draw current line being built (if any)
    if current_line_words:
        current_text = " ".join(current_line_words)
        draw_active_text(x, y, current_text)
    
    # Show counts at bottom
    canvas.create_text(600, HEIGHT-15, text=f"Words: {len(current_line_words)}/{MAX_WORDS_PER_LINE}", 
                       fill="#888888", font=("Segoe UI", 9))
    canvas.create_text(650, HEIGHT-15, text=f"Lines: {len(all_lines)}/{MAX_LINES}", 
                       fill="#66ccff", font=("Segoe UI", 10, "bold"))

def draw_text(x, y, text):
    """Draw clean text"""
    # Shadow
    canvas.create_text(x+1, y+1, text=text, fill="#1a1a1a", font=FONT, anchor="nw", width=WIDTH-50)
    # Main text
    canvas.create_text(x, y, text=text, fill="#ffffff", font=FONT, anchor="nw", width=WIDTH-50)

def draw_active_text(x, y, text):
    """Draw active text with cursor"""
    # Shadow
    canvas.create_text(x+1, y+1, text=text, fill="#1a1a1a", font=FONT, anchor="nw", width=WIDTH-50)
    # Main text
    canvas.create_text(x, y, text=text, fill="#ffffff", font=FONT, anchor="nw", width=WIDTH-50)
    
    # Blinking cursor
    if text and int(time.time() * 2) % 2:
        temp_item = canvas.create_text(x, y, text=text, font=FONT, anchor="nw")
        bbox = canvas.bbox(temp_item)
        canvas.delete(temp_item)
        if bbox:
            cursor_x = bbox[2] + 2
            cursor_y = y + (bbox[3] - bbox[1]) // 2
            canvas.create_line(cursor_x, cursor_y-12, cursor_x, cursor_y+12, 
                             fill="#66ccff", width=2, capstyle="round")

def update_text(text):
    """Called from Friday - splits text into words and queues them"""
    words = text.split()
    print(f"\n[MSG] Received {len(words)} words: '{text[:80]}...'")
    
    for word in words:
        word_queue.put(word)

def clear_overlay():
    """Clear all text"""
    global current_line_words, all_lines
    current_line_words = []
    all_lines = []
    draw()

# Start processing queue
root.after(50, process_queue)

if __name__ == "__main__":
    def test_scroll():
        # Test with 43 words (should create 3 lines)
        long_text = "I can help you with opening websites and applications playing music on YouTube monitoring your system taking screenshots extracting text from images remembering information controlling YouTube playback closing tabs and applications minimizing windows answering your questions and much more"
        update_text(long_text)
        
        # Add more lines to test scrolling
        root.after(3000, lambda: update_text("Line 2: Second response with some words"))
        root.after(6000, lambda: update_text("Line 3: Third response"))
        root.after(9000, lambda: update_text("Line 4: Fourth response"))
        root.after(12000, lambda: update_text("Line 5: Fifth response"))
        root.after(15000, lambda: update_text("Line 6: Sixth response - box will be full"))
        root.after(18000, lambda: update_text("Line 7: Seventh response - ALL lines should CLEAR"))
    
    test_scroll()
    root.mainloop()