"""Formatting shared by visual-editor previews and public reading pages."""
import bleach
import markdown


def render_markdown(text):
    renderer = markdown.Markdown(extensions=['sane_lists', 'nl2br'])
    # Keep literal HTML visible as text, matching the visual editor's CommonMark parser.
    renderer.preprocessors.deregister('html_block')
    renderer.inlinePatterns.deregister('html')
    return bleach.clean(renderer.convert(text or ''),
        tags=['p','h1','h2','h3','h4','h5','h6','em','strong','ul','ol','li','blockquote','hr','br','code','pre'],
        attributes={}, strip=True)
