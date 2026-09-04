/**
 * Client-side condition normalization — mirrors backend conditions.py.
 */

const CONDITION_MAP = {
  'new': 'New',
  'new with box': 'New',
  'new without box': 'New',
  'new with tags': 'New',
  'new without tags': 'New',
  'new other / open box': 'Open Box',
  'new other': 'Open Box',
  'open box': 'Open Box',
  'new with imperfections': 'New with Defects',
  'new with defects': 'New with Defects',
  'certified - refurbished': 'Refurbished',
  'excellent - refurbished': 'Refurbished',
  'very good - refurbished': 'Refurbished',
  'good - refurbished': 'Refurbished',
  'certified / professionally refurbished': 'Refurbished',
  'pre-owned - excellent': 'Pre-owned - Excellent',
  'pre-owned - good': 'Pre-owned - Good',
  'pre-owned': 'Pre-owned - Good',
  'used': 'Pre-owned - Good',
  'pre-owned - fair': 'Pre-owned - Fair',
  'for parts or not working': 'For Parts',
};

export function normalizeCondition(raw) {
  if (!raw) return 'Other';
  return CONDITION_MAP[raw.trim().toLowerCase()] || 'Other';
}
