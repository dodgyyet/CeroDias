from flask import Blueprint, request, render_template_string

bp = Blueprint('search', __name__)


@bp.route('/search')
def search():
    query = request.args.get('q', '')
    template = f"""{{% extends 'base.html' %}}
{{% block title %}}Search - CeroDias CTF Platform{{% endblock %}}
{{% block content %}}
<div class="container mt-4">
  <h4>Search results for: {query}</h4>
  <p class="text-muted">No results found.</p>
</div>
{{% endblock %}}"""
    return render_template_string(template)
