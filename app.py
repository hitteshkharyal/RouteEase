# Held-Karp TSP with memoization
from flask import Flask, render_template, request, redirect, url_for, session
import networkx as nx
import folium
from geopy.geocoders import Nominatim
import requests
import os
from functools import lru_cache

app = Flask(__name__)
app.secret_key = "your_secret_key"

if not os.path.exists('static'):
    os.makedirs('static')

def get_location(name):
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.geocode(name)
    if location:
        return (location.latitude, location.longitude)
    return None

def get_distance(origin, destination):
    api_url = "https://router.project-osrm.org/route/v1/driving/{},{};{},{}?overview=false"
    origin_coords = get_location(origin)
    destination_coords = get_location(destination)

    if origin_coords and destination_coords:
        url = api_url.format(origin_coords[1], origin_coords[0], destination_coords[1], destination_coords[0])
        response = requests.get(url).json()
        if "routes" in response and response["routes"]:
            return response["routes"][0]["distance"] / 1000
    return float('inf')

def held_karp(graph, cities):
    n = len(cities)
    index_map = {city: idx for idx, city in enumerate(cities)}

    @lru_cache(maxsize=None)
    def tsp(mask, pos):
        if mask == (1 << n) - 1:
            return graph[cities[pos]][cities[0]]['weight']

        ans = float('inf')
        for city in range(n):
            if mask & (1 << city) == 0:
                ans = min(ans, graph[cities[pos]][cities[city]]['weight'] + tsp(mask | (1 << city), city))
        return ans

    @lru_cache(maxsize=None)
    def find_path(mask, pos):
        if mask == (1 << n) - 1:
            return [cities[pos], cities[0]]
        best = float('inf')
        best_city = -1
        for city in range(n):
            if mask & (1 << city) == 0:
                cost = graph[cities[pos]][cities[city]]['weight'] + tsp(mask | (1 << city), city)
                if cost < best:
                    best = cost
                    best_city = city
        return [cities[pos]] + find_path(mask | (1 << best_city), best_city)

    min_distance = tsp(1, 0)
    best_route = find_path(1, 0)
    node_distances = [(best_route[i], best_route[i+1], graph[best_route[i]][best_route[i+1]]['weight']) for i in range(n)]
    return best_route, min_distance, node_distances

def visualize_route(graph, path, locations, node_distances):
    start_coords = locations[path[0]]
    m = folium.Map(location=start_coords, zoom_start=6)
    for node in path:
        folium.Marker(location=locations[node], popup=node, icon=folium.Icon(color='blue')).add_to(m)
    for city1, city2, distance in node_distances:
        folium.PolyLine([locations[city1], locations[city2]], color='red', weight=3,
                        tooltip=f"{city1} ↔ {city2}: {distance:.2f} km").add_to(m)
    return m

@app.route('/', methods=['GET', 'POST'])
def select_cities():
    if request.method == 'POST':
        num_cities = int(request.form['num_cities'])
        return redirect(url_for('enter_cities', num_cities=num_cities))
    return render_template('select_cities.html')

@app.route('/enter_cities/<int:num_cities>', methods=['GET', 'POST'])
def enter_cities(num_cities):
    if request.method == 'POST':
        cities = [request.form[f'city{i}'] for i in range(1, num_cities + 1)]
        city_graph = nx.Graph()
        locations = {city: get_location(city) for city in cities}

        for city, coords in locations.items():
            if coords:
                city_graph.add_node(city)

        for i in range(len(cities)):
            for j in range(i + 1, len(cities)):
                city1, city2 = cities[i], cities[j]
                if city1 in city_graph and city2 in city_graph:
                    distance = get_distance(city1, city2)
                    if distance:
                        city_graph.add_weighted_edges_from([(city1, city2, distance)])

        if len(city_graph.nodes) == len(cities):
            best_route, min_distance, node_distances = held_karp(city_graph, cities)
            if best_route:
                route_map = visualize_route(city_graph, best_route, locations, node_distances)
                map_path = "static/route_map.html"
                route_map.save(map_path)

                session['path'] = best_route
                session['min_distance'] = min_distance
                session['node_distances'] = node_distances

                return redirect(url_for('show_map'))
            else:
                return render_template('map.html', error="No valid route found between the cities.")
        else:
            return render_template('map.html', error="Failed to fetch distances for all cities.")

    return render_template('enter_cities.html', num_cities=num_cities)

@app.route('/map')
def show_map():
    if 'path' in session:
        path = session['path']
        min_distance = session['min_distance']
        node_distances = session['node_distances']
        map_path = "static/route_map.html"

        return render_template(
            'map.html',
            path=path,
            min_distance=int(min_distance),
            node_distances=node_distances,
            map_path=map_path
        )
    else:
        return "No map data available. Please run the route finder first."

if __name__ == '__main__':
    app.run(debug=True)

