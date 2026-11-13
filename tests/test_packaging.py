from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from backend import main
from backend.services import model_service
from scripts.setup import restore_database, verify_database, install_model

class PackagingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ai-calories-')
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'nutrition.db'
        restore_database(self.db)
        self.override = patch.object(main, 'DB_PATH', self.db)
        self.override.start()
        self.addCleanup(self.override.stop)
        self.client = TestClient(main.app)

    def test_seed_idempotent_integrity_unicode(self):
        self.assertEqual(verify_database(self.db, exact=True)['ingredients'],88)
        before = self.db.read_bytes()
        restore_database(self.db)
        self.assertEqual(before,self.db.read_bytes())
        self.assertIn('Cơm tấm',self.client.get('/recipes/1').json()['food_name'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(dict((r[1],r[2]) for r in db.execute('pragma table_info(foods)'))['model_class_index'],'INTEGER')

    def test_api_profiles_and_nutrition(self):
        self.assertEqual(self.client.get('/').json(),{'app':'AI Calories','status':'running'})
        self.assertEqual(len(self.client.get('/ingredients').json()),88)
        counts = {}
        for rid in range(1,78):
            recipe=self.client.get(f'/recipes/{rid}').json()
            counts[recipe['profile_type']]=counts.get(recipe['profile_type'],0)+1
        self.assertEqual(counts,{'ingredient_recipe':1,'as_served_reference':76})
        recipe=self.client.get('/recipes/1').json()
        response=self.client.post('/recipes/1/calculate',json={'components':[{'ingredient_id':x['ingredient_id'],'grams':x['grams']} for x in recipe['components']]} )
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()['nutrition']['nutrients']),21)
        self.assertTrue(any(n['amount'] is None for n in response.json()['nutrition']['nutrients'].values()))
        self.assertFalse(self.client.get('/foods/by-canonical/unknown').json()['mapped'])
        self.assertEqual(self.client.get('/recipes/9999').status_code,404)
        self.assertEqual(self.client.post('/recipes/1/calculate',json={'components':[]}).status_code,422)
        recipe=self.client.get('/recipes/2').json()
        component=recipe['components'][0]
        a=self.client.post('/recipes/2/calculate',json={'components':[{'ingredient_id':component['ingredient_id'],'grams':100}]}).json()
        b=self.client.post('/recipes/2/calculate',json={'components':[{'ingredient_id':component['ingredient_id'],'grams':200}]}).json()
        self.assertAlmostEqual(b['nutrition']['nutrients']['energy']['amount'],2*a['nutrition']['nutrients']['energy']['amount'],places=1)

    def test_restore_confirmation_and_download(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("INSERT INTO ingredients VALUES (999, 'local', NULL, 'raw')")
        restore_database(self.db)
        self.assertEqual(verify_database(self.db)['ingredients'],89)
        restore_database(self.db, overwrite=True)
        self.assertEqual(verify_database(self.db,exact=True)['ingredients'],88)
        self.assertEqual(verify_database(self.db.with_name('nutrition.db.before-restore.bak'))['ingredients'],89)
        target=Path(self.temp.name)/'download.pth'
        with model_service.CHECKPOINT_PATH.open('rb') as source:
            with patch('urllib.request.urlopen',return_value=source):
                install_model(target)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                         hashlib.sha256(model_service.CHECKPOINT_PATH.read_bytes()).hexdigest())

    def test_cors_and_upload_errors(self):
        r=self.client.options('/predict',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
        self.assertEqual(r.headers['access-control-allow-origin'],'http://localhost:5173')
        self.assertNotIn('access-control-allow-origin',self.client.options('/predict',headers={'Origin':'https://untrusted.example','Access-Control-Request-Method':'POST'}).headers)
        self.assertEqual(self.client.post('/predict',files={'file':('x.txt',b'x','text/plain')}).status_code,415)
        self.assertEqual(self.client.post('/predict',files={'file':('x.png',b'bad','image/png')}).status_code,400)

    def test_real_prediction_and_missing_checkpoint(self):
        image=io.BytesIO();Image.new('RGB',(224,224),(120,80,40)).save(image,format='PNG')
        r=self.client.post('/predict?top_k=3',files={'file':('smoke.png',image.getvalue(),'image/png')})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['taxonomy_version'],'unified-food-4-v2')
        classifier=model_service.get_classifier()
        self.assertEqual(len(classifier.classes),310)
        with closing(sqlite3.connect(self.db)) as db:
            for canonical,index in db.execute('select canonical_id,model_class_index from foods'):
                self.assertEqual(classifier.classes[index]['canonical_id'],canonical)
        for p in r.json()['predictions']:
            self.assertEqual(classifier.classes[p['model_index']]['canonical_id'],p['canonical_id'])
        model_service.get_classifier.cache_clear()
        with patch.object(model_service,'CHECKPOINT_PATH',Path(self.temp.name)/'missing.pth'):
            r=self.client.post('/predict',files={'file':('smoke.png',image.getvalue(),'image/png')})
            self.assertEqual(r.status_code,503)
            self.assertIn('setup.py',r.json()['detail'])
        bad=Path(self.temp.name)/'bad.pth';bad.write_bytes(b'invalid')
        with self.assertRaisesRegex(ValueError,'checksum'):
            install_model(Path(self.temp.name)/'target.pth',bad)
        self.assertFalse((Path(self.temp.name)/'target.pth').exists())

if __name__ == '__main__': unittest.main()
