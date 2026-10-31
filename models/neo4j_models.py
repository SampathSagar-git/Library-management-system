import logging
import os
from collections import defaultdict
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class FallbackGraphStore:
    """
    High-fidelity in-memory graph engine implementing the exact Cypher graph
    nodes, relationships, and traversal recommendations when Neo4j is offline.
    """
    def __init__(self):
        self.nodes = {
            "Student": {},
            "Staff": {},
            "Book": {},
            "Author": {},
            "Category": {},
            "Desk": {}
        }
        # Edges stored as (from_label, from_id, rel_type, to_label, to_id, props)
        self.edges = []
        logger.info("[Neo4j Service] Resilient in-memory graph engine initialized.")

    def add_node(self, label, node_id, props):
        if label not in self.nodes:
            self.nodes[label] = {}
        props['id'] = str(node_id)
        self.nodes[label][str(node_id)] = props

    def add_edge(self, from_label, from_id, rel_type, to_label, to_id, props=None):
        props = props or {}
        # Avoid duplicate edges of same type between same nodes
        for e in self.edges:
            if (e['from_label'] == from_label and e['from_id'] == str(from_id) and
                e['rel_type'] == rel_type and e['to_label'] == to_label and e['to_id'] == str(to_id)):
                e['props'].update(props)
                return
        self.edges.append({
            'from_label': from_label,
            'from_id': str(from_id),
            'rel_type': rel_type,
            'to_label': to_label,
            'to_id': str(to_id),
            'props': props
        })

    def get_borrowed_books(self, user_id):
        borrowed_book_ids = set()
        for e in self.edges:
            if e['from_id'] == str(user_id) and e['rel_type'] == 'BORROWED':
                borrowed_book_ids.add(e['to_id'])
        return borrowed_book_ids

    def recommend_books_for_user(self, user_id, user_role="student", limit=6):
        user_id_str = str(user_id)
        user_borrowed = self.get_borrowed_books(user_id_str)
        
        # User's interests
        user_interests = set()
        for e in self.edges:
            if e['from_id'] == user_id_str and e['rel_type'] == 'INTERESTED_IN':
                user_interests.add(e['to_id']) # category name or id
        
        scores = defaultdict(int)
        reasons = defaultdict(list)
        
        # 1. Collaborative filtering: Who borrowed what I borrowed?
        co_borrowers = set()
        for e in self.edges:
            if e['rel_type'] == 'BORROWED' and e['to_id'] in user_borrowed and e['from_id'] != user_id_str:
                co_borrowers.add(e['from_id'])
                
        for e in self.edges:
            if e['rel_type'] == 'BORROWED' and e['from_id'] in co_borrowers:
                b_id = e['to_id']
                if b_id not in user_borrowed:
                    scores[b_id] += 3
                    reasons[b_id].append("Readers with similar reading tastes also enjoyed this")

        # 2. Category interest matching
        for b_id, b_props in self.nodes.get("Book", {}).items():
            if b_id in user_borrowed:
                continue
            cat = b_props.get('category')
            if cat and cat in user_interests:
                scores[b_id] += 2
                reasons[b_id].append(f"Matches your topic of interest in {cat}")

        # 3. Author matching
        user_authors = set()
        for b_id in user_borrowed:
            book_props = self.nodes.get("Book", {}).get(b_id, {})
            if book_props.get('author'):
                user_authors.add(book_props['author'])
                
        for b_id, b_props in self.nodes.get("Book", {}).items():
            if b_id in user_borrowed:
                continue
            if b_props.get('author') and b_props.get('author') in user_authors:
                scores[b_id] += 2
                reasons[b_id].append(f"More from author {b_props.get('author')}")

        # 4. Global popularity fallback if scores are sparse
        if len(scores) < limit:
            for e in self.edges:
                if e['rel_type'] == 'BORROWED':
                    b_id = e['to_id']
                    if b_id not in user_borrowed and b_id not in scores:
                        scores[b_id] += 1
                        reasons[b_id].append("Frequently borrowed campus favorite")

        sorted_books = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        results = []
        for b_id, score in sorted_books:
            b_props = self.nodes.get("Book", {}).get(b_id)
            if b_props:
                item = dict(b_props)
                item['score'] = score
                item['recommendation_reason'] = reasons[b_id][0] if reasons[b_id] else "Recommended library resource"
                results.append(item)
        return results

    def get_stats(self):
        return {
            'total_nodes': sum(len(n) for n in self.nodes.values()),
            'node_counts': {k: len(v) for k, v in self.nodes.items()},
            'total_relationships': len(self.edges),
            'relationship_types': {
                'BORROWED': len([e for e in self.edges if e['rel_type'] == 'BORROWED']),
                'RESERVED': len([e for e in self.edges if e['rel_type'] == 'RESERVED']),
                'BOOKED': len([e for e in self.edges if e['rel_type'] == 'BOOKED']),
                'WRITTEN_BY': len([e for e in self.edges if e['rel_type'] == 'WRITTEN_BY']),
                'BELONGS_TO': len([e for e in self.edges if e['rel_type'] == 'BELONGS_TO']),
                'INTERESTED_IN': len([e for e in self.edges if e['rel_type'] == 'INTERESTED_IN']),
            }
        }

    def get_visualization(self, limit=50):
        elements = {'nodes': [], 'edges': []}
        count = 0
        added_node_ids = set()
        
        for e in self.edges[:limit]:
            from_key = f"{e['from_label']}_{e['from_id']}"
            to_key = f"{e['to_label']}_{e['to_id']}"
            
            if from_key not in added_node_ids:
                from_props = self.nodes.get(e['from_label'], {}).get(e['from_id'], {})
                elements['nodes'].append({
                    'id': from_key,
                    'label': from_props.get('name') or from_props.get('title') or e['from_id'],
                    'group': e['from_label']
                })
                added_node_ids.add(from_key)
                
            if to_key not in added_node_ids:
                to_props = self.nodes.get(e['to_label'], {}).get(e['to_id'], {})
                elements['nodes'].append({
                    'id': to_key,
                    'label': to_props.get('title') or to_props.get('name') or e['to_id'],
                    'group': e['to_label']
                })
                added_node_ids.add(to_key)
                
            elements['edges'].append({
                'from': from_key,
                'to': to_key,
                'label': e['rel_type']
            })
        return elements


class Neo4jService:
    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or os.environ.get('NEO4J_USER', 'neo4j')
        self.password = password or os.environ.get('NEO4J_PASSWORD', 'library123')
        self.driver = None
        self.is_live = False
        self.fallback = FallbackGraphStore()
        self.connect()

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password), connection_timeout=1.5)
            self.driver.verify_connectivity()
            self.is_live = True
            logger.info(f"Connected successfully to live Neo4j database at {self.uri}")
            self.init_constraints()
        except Exception as e:
            logger.warning(f"Could not connect to Neo4j database ({e}). Operating in resilient graph emulation mode.")
            self.is_live = False

    def close(self):
        if self.driver:
            self.driver.close()

    def init_constraints(self):
        if not self.is_live:
            return
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Student) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Staff) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Book) REQUIRE b.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Desk) REQUIRE d.number IS UNIQUE"
        ]
        with self.driver.session() as session:
            for query in constraints:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug(f"Constraint notice: {e}")

    # ================== Node Creation / Sync ==================

    def sync_user(self, user_id, name, email, role, department="General"):
        label = "Staff" if role == "staff" else "Student"
        props = {"id": str(user_id), "name": name, "email": email, "department": department}
        self.fallback.add_node(label, str(user_id), props)
        
        if self.is_live:
            query = f"""
            MERGE (u:{label} {{id: $id}})
            SET u.name = $name, u.email = $email, u.department = $department
            """
            try:
                with self.driver.session() as session:
                    session.run(query, id=str(user_id), name=name, email=email, department=department)
            except Exception as e:
                logger.error(f"Neo4j sync_user failed: {e}")

    def sync_book(self, book_id, title, author, isbn, category):
        book_props = {"id": str(book_id), "title": title, "author": author, "isbn": isbn, "category": category}
        self.fallback.add_node("Book", str(book_id), book_props)
        self.fallback.add_node("Author", author, {"name": author})
        self.fallback.add_node("Category", category, {"name": category})
        self.fallback.add_edge("Book", str(book_id), "WRITTEN_BY", "Author", author)
        self.fallback.add_edge("Book", str(book_id), "BELONGS_TO", "Category", category)

        if self.is_live:
            query = """
            MERGE (b:Book {id: $book_id})
            SET b.title = $title, b.isbn = $isbn, b.category = $category, b.author = $author
            MERGE (a:Author {name: $author})
            MERGE (c:Category {name: $category})
            MERGE (b)-[:WRITTEN_BY]->(a)
            MERGE (b)-[:BELONGS_TO]->(c)
            """
            try:
                with self.driver.session() as session:
                    session.run(query, book_id=str(book_id), title=title, author=author, isbn=isbn, category=category)
            except Exception as e:
                logger.error(f"Neo4j sync_book failed: {e}")

    def sync_desk(self, desk_number, zone):
        self.fallback.add_node("Desk", desk_number, {"number": desk_number, "zone": zone})
        if self.is_live:
            query = """
            MERGE (d:Desk {number: $number})
            SET d.zone = $zone
            """
            try:
                with self.driver.session() as session:
                    session.run(query, number=desk_number, zone=zone)
            except Exception as e:
                logger.error(f"Neo4j sync_desk failed: {e}")

    # ================== Relationship Operations ==================

    def record_borrow(self, user_id, book_id, role="student", loan_id=None):
        label = "Staff" if role == "staff" else "Student"
        self.fallback.add_edge(label, str(user_id), "BORROWED", "Book", str(book_id), {"loan_id": str(loan_id)})

        if self.is_live:
            query = f"""
            MATCH (u:{label} {{id: $user_id}})
            MATCH (b:Book {{id: $book_id}})
            MERGE (u)-[r:BORROWED {{loan_id: $loan_id}}]->(b)
            SET r.timestamp = datetime()
            """
            try:
                with self.driver.session() as session:
                    session.run(query, user_id=str(user_id), book_id=str(book_id), loan_id=str(loan_id))
            except Exception as e:
                logger.error(f"Neo4j record_borrow failed: {e}")

    def record_reservation(self, user_id, book_id, role="student"):
        label = "Staff" if role == "staff" else "Student"
        self.fallback.add_edge(label, str(user_id), "RESERVED", "Book", str(book_id))

        if self.is_live:
            query = f"""
            MATCH (u:{label} {{id: $user_id}})
            MATCH (b:Book {{id: $book_id}})
            MERGE (u)-[r:RESERVED]->(b)
            SET r.timestamp = datetime()
            """
            try:
                with self.driver.session() as session:
                    session.run(query, user_id=str(user_id), book_id=str(book_id))
            except Exception as e:
                logger.error(f"Neo4j record_reservation failed: {e}")

    def record_desk_booking(self, user_id, desk_number, role="student", booking_date=None, start_time=None):
        label = "Staff" if role == "staff" else "Student"
        self.fallback.add_edge(label, str(user_id), "BOOKED", "Desk", str(desk_number), {
            "date": booking_date, "start_time": start_time
        })

        if self.is_live:
            query = f"""
            MATCH (u:{label} {{id: $user_id}})
            MATCH (d:Desk {{number: $desk_number}})
            CREATE (u)-[r:BOOKED {{date: $date, start_time: $start_time, created_at: datetime()}}]->(d)
            """
            try:
                with self.driver.session() as session:
                    session.run(query, user_id=str(user_id), desk_number=str(desk_number), date=booking_date, start_time=start_time)
            except Exception as e:
                logger.error(f"Neo4j record_desk_booking failed: {e}")

    def record_user_interest(self, user_id, category_name, role="student"):
        label = "Staff" if role == "staff" else "Student"
        self.fallback.add_node("Category", category_name, {"name": category_name})
        self.fallback.add_edge(label, str(user_id), "INTERESTED_IN", "Category", category_name)

        if self.is_live:
            query = f"""
            MATCH (u:{label} {{id: $user_id}})
            MERGE (c:Category {{name: $category_name}})
            MERGE (u)-[:INTERESTED_IN]->(c)
            """
            try:
                with self.driver.session() as session:
                    session.run(query, user_id=str(user_id), category_name=category_name)
            except Exception as e:
                logger.error(f"Neo4j record_user_interest failed: {e}")

    # ================== Recommendation Engine ==================

    def get_recommendations(self, user_id, role="student", limit=6):
        """
        Calculates graph recommendations using collaborative filtering and category/author traversals.
        """
        # Always run fallback engine as backup or primary
        fallback_recs = self.fallback.recommend_books_for_user(user_id, role, limit)
        
        if not self.is_live:
            return fallback_recs

        label = "Staff" if role == "staff" else "Student"
        query = f"""
        MATCH (u:{label} {{id: $user_id}})
        OPTIONAL MATCH (u)-[:BORROWED]->(b:Book)<-[:BORROWED]-(other)-[:BORROWED]->(rec:Book)
        WHERE NOT (u)-[:BORROWED]->(rec)
        WITH rec, count(DISTINCT other) AS score, "Readers with similar reading tastes also enjoyed this" AS reason
        WHERE rec IS NOT NULL
        RETURN rec.id AS id, rec.title AS title, rec.author AS author, rec.category AS category, score, reason
        ORDER BY score DESC LIMIT $limit
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, user_id=str(user_id), limit=limit)
                records = [dict(record) for record in result]
                if records:
                    return records
        except Exception as e:
            logger.error(f"Neo4j get_recommendations query failed: {e}")
            
        return fallback_recs

    def get_graph_stats(self):
        if not self.is_live:
            return self.fallback.get_stats()
            
        try:
            with self.driver.session() as session:
                nodes_res = session.run("MATCH (n) RETURN count(n) AS total_nodes")
                rels_res = session.run("MATCH ()-[r]->() RETURN count(r) AS total_relationships")
                total_nodes = nodes_res.single()["total_nodes"]
                total_rels = rels_res.single()["total_relationships"]
                return {
                    'total_nodes': total_nodes,
                    'total_relationships': total_rels,
                    'is_live': True
                }
        except Exception as e:
            logger.error(f"Neo4j get_graph_stats failed: {e}")
            return self.fallback.get_stats()

    def get_graph_visualization(self, limit=40):
        return self.fallback.get_visualization(limit)

# Global singleton
neo4j_service = Neo4jService()
