from dataclasses import dataclass
import collections
import re
import os
import io

import paths
import tokenizer
import pandas as pd
import matplotlib.pyplot as plt
from itertools import islice



@dataclass
class TextAnalytics:
    num_tokens: int
    token_histogram: collections.Counter

    def __init__(self, splits=None):
        if splits is None:
            splits = []
        self.token_histogram = collections.Counter(splits)
        self.num_tokens = len(self.token_histogram)

    def print_histogram(self):
        for token, count in self.token_histogram.items():
            print(repr(token), count)

    def get_histogram_as_string(self):
        s = ""
        for token, count in self.token_histogram.items():
            s += repr(token) + " " + str(count) + "\n"
        return s

    def combine(self, analytics: 'TextAnalytics'):
        self.token_histogram += analytics.token_histogram
        self.num_tokens = len(self.token_histogram)

@dataclass
class FolderAnalytics:
    num_texts: int
    analytics: TextAnalytics

    def print_histogram(self):
        self.analytics.print_histogram()

    def combine(self, folder_analytics: 'FolderAnalytics'):
        self.num_texts += folder_analytics.num_texts
        self.analytics.combine(folder_analytics.analytics)

# Analytics for a single page
def analyze_text(text: str) -> TextAnalytics:
    tokens = tokenizer.split_text(text)
    return TextAnalytics(tokens)

def analyze_file(file_name: str | None = None) -> TextAnalytics:
    if file_name is None:
        file_name = paths.select_file(paths.WIKIPEDIA_DATA_PATH, choose_file=True)
    # print(file_name)
    with open(file_name, 'r') as f:
        text = f.read()
        return analyze_text(text)

def analyze_folder(folder_name: str | None = None) -> FolderAnalytics:
    if folder_name is None:
        folder_name = paths.select_file(paths.WIKIPEDIA_DATA_PATH, choose_file=False)
    print(folder_name)

    # First get list of all files within this folder.
    file_names = [f.path for f in os.scandir(folder_name) if f.name.endswith("txt")]

    # Then get analytics of this folder
    text_analytics = TextAnalytics()
    for file in file_names:
        text_analytics.combine(analyze_file(file))
    folder_analytics = FolderAnalytics(len(file_names), text_analytics)

    # Then search for subfolders and get their analytics
    subfolder_names = [f.path for f in os.scandir(folder_name) if f.is_dir() and f.name != paths.UNALTERED_FOLDER_NAME]
    for subfolder in subfolder_names:
        folder_analytics.combine(analyze_folder(subfolder))

    # Save this in a file at the selected folder.
    analytics_path = folder_name + "/.analytics"
    with open(analytics_path, "w") as f:
        f.write("num texts: " + str(folder_analytics.num_texts))
        f.write("\nnum tokens: " + str(folder_analytics.analytics.num_tokens))
        f.write('\n\n' + folder_analytics.analytics.get_histogram_as_string())
        print("analytics saved at: ", analytics_path)

    # Return combined analytics
    return folder_analytics

# Find a way to do this directly with the .analytics file
def display_analytics(analytics: FolderAnalytics | TextAnalytics | None = None):
    if isinstance(analytics, FolderAnalytics):
        histogram = analytics.analytics.token_histogram
    elif isinstance(analytics, TextAnalytics):
        histogram = analytics.token_histogram
    else:
        filename = paths.select_file(init_dir=paths.WIKIPEDIA_DATA_PATH, choose_file=True)
        histogram = convert_file_to_histogram(filename)
    df = pd.DataFrame({'category': list(histogram.keys()),
                       'number': list(histogram.values())})
    df.set_index('category', inplace=True)
    df.sort_values('number', inplace=True)
    df.plot(y='number', kind='bar', legend=False)
    plt.show()

# This is messy
def convert_file_to_histogram(filename: str):
    line_count = 0
    hist = {}
    with io.open(filename, 'r') as f:
        for line in f:
            if line_count > 2:
                splits = line.split()
                key = splits[0]
                count = int(splits[1])
                hist[key] = count
            line_count += 1
    hist = dict(sorted(hist.items(), key=lambda item: item[1]))
    return hist



if __name__ == "__main__":

    ## This is the example test
    # text1 = "Canada Oil and Gas Operations Act ( R.S., 1985, c. O-7 )\n\n The following are numbers: 1.42, -3, 483, 1E-4, -23.1"
    # text2 = "BSI created one of the world's first quality marks in 1903, when the letters 'B' and 'S' (for British Standard) were combined with V (for verification) to produce the Kitemark logo."
    # analytics1 = analyze_text(text1)
    # analytics2 = analyze_text(text2)
    #
    # analytics1.combine(analytics2)
    # analytics1.print_histogram()
    # display_analytics(analytics1)

    ## This analyzes a file
    # file_text_analytics = analyze_file()
    # file_text_analytics.print_histogram()

    # This analyzes a folder
    folder_analytics = analyze_folder()
    print("num texts: ", folder_analytics.num_texts)
    print("num tokens: ", folder_analytics.analytics.num_tokens)

    # display_analytics()


