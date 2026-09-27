/* Enhance server-rendered list forms without requiring external libraries. */
(() => {
  const forms = [...document.querySelectorAll('form.list-controls')];
  if (!forms.length || !window.fetch || !window.AbortController) return;
  const controls = forms.flatMap(form => [...form.querySelectorAll('input[type="search"], select')]);
  const status = document.createElement('p');
  status.className = 'muted';
  status.setAttribute('role', 'status');
  status.hidden = true;
  forms[0].before(status);
  let timer;
  let controller;
  let generation = 0;
  let appliedURL = new URL(window.location.href);

  function clearLoading() {
    document.querySelectorAll('.list-loading').forEach(region => {
      region.classList.remove('list-loading');
      region.removeAttribute('aria-busy');
      region.removeAttribute('aria-label');
      region.inert = false;
    });
  }

  function showLoading(url) {
    forms.forEach(form => {
      const fields = [...form.querySelectorAll('input[type="search"], select')];
      const changed = fields.some(field => {
        const fallback = field.tagName === 'SELECT' ? 'newest' : '';
        return (url.searchParams.get(field.name) || fallback) !== (appliedURL.searchParams.get(field.name) || fallback);
      });
      const region = form.nextElementSibling;
      if (changed && region && region.matches('[data-list-results]')) {
        region.classList.add('list-loading');
        region.setAttribute('aria-busy', 'true');
        region.setAttribute('aria-label', 'Loading results');
        region.inert = true;
      }
    });
  }

  function cancel() {
    clearTimeout(timer);
    if (controller) controller.abort();
    generation += 1;
    clearLoading();
  }

  function currentURL() {
    const url = new URL(window.location.href);
    controls.forEach(control => url.searchParams.set(control.name, control.value));
    return url;
  }

  function syncForms(url) {
    forms.forEach(form => {
      [...form.elements].forEach(control => {
        if (!control.name) return;
        if (control.tagName === 'SELECT') {
          const value = url.searchParams.get(control.name) || 'newest';
          control.value = [...control.options].some(option => option.value === value) ? value : 'newest';
        } else {
          control.value = url.searchParams.get(control.name) || '';
        }
      });
    });
  }

  async function update(url, historyMode = 'replace') {
    cancel();
    const version = generation;
    controller = new AbortController();
    const regions = [...document.querySelectorAll('[data-list-results]')];
    regions.forEach(region => region.setAttribute('aria-busy', 'true'));
    status.textContent = 'Updating results…';
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin'});
      if (!response.ok) throw new Error('Request failed');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (version !== generation) return;
      const replacements = regions.map(region => page.getElementById(region.id));
      if (replacements.some(region => !region)) throw new Error('Missing results');
      regions.forEach((region, index) => region.replaceWith(replacements[index]));
      appliedURL = new URL(url);
      if (historyMode === 'replace') history.replaceState(null, '', url);
      // Keep hidden fields and clear links accurate for native form fallback.
      forms.forEach((form, index) => {
        const fresh = page.querySelectorAll('form.list-controls')[index];
        form.querySelectorAll('input[type="hidden"]').forEach(input => {
          input.value = fresh.elements.namedItem(input.name).value;
        });
        form.querySelector('a').href = fresh.querySelector('a').href;
      });
      status.textContent = '';
    } catch (error) {
      if (version === generation && error.name !== 'AbortError') {
        status.hidden = false;
        status.textContent = 'Could not update results. Change a filter or press Enter in the search field to retry.';
      }
    } finally {
      if (version === generation) clearLoading();
    }
  }

  forms.forEach(form => {
    form.addEventListener('submit', event => {
      event.preventDefault();
      update(currentURL());
    });
    form.querySelector('a').addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      form.querySelectorAll('input[type="search"], select').forEach(control => {
        control.value = control.tagName === 'SELECT' ? 'newest' : '';
      });
      update(currentURL());
    });
  });
  controls.forEach(control => {
    control.addEventListener(control.tagName === 'SELECT' ? 'change' : 'input', () => {
      cancel();
      if (control.tagName === 'SELECT') update(currentURL());
      else timer = setTimeout(() => update(currentURL()), 250);
    });
  });
  window.addEventListener('popstate', () => {
    const url = new URL(window.location.href);
    syncForms(url);
    update(url, 'none');
  });
  // Native submit buttons are only needed when live filtering is unavailable.
  forms.forEach(form => {
    form.querySelectorAll('button[type="submit"]').forEach(button => button.remove());
  });
})();
