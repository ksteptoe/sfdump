---
orphan: true
---

# Changelog

## v2.4.15

### Viewer Two-View Architecture

- **Explorer as default view**: The viewer now opens in full-width Explorer mode — document search is front and center with no sidebar clutter
- **DB Viewer mode**: Click "DB Viewer" button (top-right) to switch to the record browser with sidebar controls, relationship navigation, and subtree documents
- **Seamless bridging**: "Open parent record" in Explorer automatically switches to DB Viewer with the correct record selected
- **Back to Explorer**: One-click return from DB Viewer sidebar
- **Debug cleanup**: Removed debug expanders from production UI

## v2.4.14

### Document Explorer Improvements

- **Search-first UI**: The search box is now the primary input, front and center
- **Wildcard support**: Use `*` (any characters), `?` (single character), and `[1-5]` (ranges)
  - Example: `PIN01006*` finds PIN010060, PIN010061, etc.
  - Example: `PIN0100[6-9]*` finds PIN01006x through PIN01009x
- **Search tips**: Click the expandable "Search tips" section for pattern examples
- **Record name first**: Results now show record_name (PIN/SIN) before file_name
- **Cleaner filters**: Account, Opportunity, and Object Type filters moved to collapsible "Additional Filters"
- **PDF only**: Renamed from "PDF first" and defaults to unchecked

### Other Changes

- Disabled Streamlit usage statistics collection by default
- Updated documentation for finance users

## v2.4.13

- Document Explorer UI improvements for finance users
- Glob-style wildcard support in search
- Moved glob_to_regex to utils module for better test coverage

## Since v1.2.0

- CHANGELOG.md from make changelog-md (fe07240) - Add changelog+changelog-md targets and a meta release task that runs tests, shows changes since last tag, and tags patch/minor/major releases (6df3700)
