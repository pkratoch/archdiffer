#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 11 22:01:26 2018

@author: pavla
"""

STATE_NEW = 0
STATE_DONE = 1
STATE_STRINGS = {
    STATE_NEW: 'new',
    STATE_DONE: 'done',
}

CATEGORY_TAGS = 0
CATEGORY_PRCO = 1
CATEGORY_FILES = 2
CATEGORY_STRINGS = {
    CATEGORY_TAGS: 'tags',
    CATEGORY_PRCO: 'PRCO',
    CATEGORY_FILES: 'files',
}

DIFF_TYPE_REMOVED = 0
DIFF_TYPE_ADDED = 1
DIFF_TYPE_CHANGED = 2
DIFF_TYPE_RENAMED = 3
DIFF_TYPE_STRINGS = {
    DIFF_TYPE_REMOVED: 'removed',
    DIFF_TYPE_ADDED: 'added',
    DIFF_TYPE_CHANGED: 'changed',
    DIFF_TYPE_RENAMED: 'renamed',
}