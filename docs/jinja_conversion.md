React (JSX) -> Jinja2 Dönüşüm Rehberi

1) useState mantığını sunucuda modellemek
- React'te `useState` ile tutulan veriler client-state'tir.
- Flask tarafında aynı veriyi dinamik olarak hesaplamak için endpoint içinde hesaplayıp `render_template()` ile Jinja2'ye gönderirsiniz.

Örnek (React):

```jsx
const [payroll, setPayroll] = useState([]);
useEffect(()=>{
  fetch('/api/bordro').then(r=>r.json()).then(setPayroll)
},[])
```

Jinja2 yaklaşımı (Flask):

```python
# app.py içinde
results = compute_payroll()
return render_template('bordro.html', results=results)
```

Jinja2 template (`bordro.html`):

```html
<ul>
  {% for r in results %}
    <li>{{ r.name }} - {{ r.payroll }}</li>
  {% endfor %}
</ul>
```

2) `.map()` -> `{% for %}` örneği

React (JSX):
```jsx
{employees.map(e => (
  <div key={e.id}>{e.first_name} {e.last_name}</div>
))}
```

Jinja2:
```html
{% for e in employees %}
  <div>{{ e.first_name }} {{ e.last_name }}</div>
{% endfor %}
```

3) Tailwind/Styles
- CSS utility sınıfları (ör. Tailwind) doğrudan Jinja2 içinde kullanılabilir. Stil dosyalarınızı `static/` içinde tutun ve base template'te include edin:

```html
<link href="{{ url_for('static', filename='css/tailwind.css') }}" rel="stylesheet">
```

4) Özet
- Client-side etkileşim için endpoint + küçük API'ler yapın, sonra Jinja2 içinde döngü ve koşullarla render edin.
- Karma bir yaklaşımda React component'leri API'leri tüketmeye devam eder; eğer tamamen sunucu tarafına geçiyorsanız `useState`'teki mantığı view fonksiyonlarında uygulayın.
 
Not: Türkçe karakterler için Flask JSON çıktılarında karakterlerin korunması önemli. Bunun için uygulama yapılandırmasında `app.config['JSON_AS_ASCII'] = False` olmalıdır ve şablon dosyalarınız UTF-8 olarak kaydedilmiş olmalıdır. Dahili örnek şablonlarda `<meta charset="utf-8">` bulunmaktadır.
