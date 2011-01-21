from __future__ import with_statement

import re

from flask import Flask, Response, render_template, jsonify
from flaskext.testing import TestCase as _TestCase
from flaskext.wtf import Form, TextField, FileField, HiddenField, \
    SubmitField, Required, FieldList

class TestCase(_TestCase):
    
    def create_app(self):
        
        class MyForm(Form):
            name = TextField("Name", validators=[Required()])
            submit = SubmitField("Submit")

        class HiddenFieldsForm(Form):
            name = HiddenField()
            url = HiddenField()
            method = HiddenField()
            secret = HiddenField()
            submit = SubmitField("Submit")

            def __init__(self, *args, **kwargs):
                super(HiddenFieldsForm, self).__init__(*args, **kwargs)
                self.method.name = '_method'

        class SimpleForm(Form):
            pass

        app = Flask(__name__)
        app.secret_key = "secret"
        
        @app.route("/", methods=("GET", "POST"))
        def index():
            
            form = MyForm()
            if form.validate_on_submit():
                name = form.name.data.upper()
            else:
                name = ''
            
            return render_template("index.html", 
                                   form=form,
                                   name=name)

        @app.route("/simple/", methods=("POST",))
        def simple():
            form = SimpleForm()
            form.validate()
            assert form.csrf_enabled
            assert not form.validate()
            assert not form.validate()
            return Response("OK")

        @app.route("/hidden/")
        def hidden():

            form = HiddenFieldsForm()
            return render_template("hidden.html", form=form)

        @app.route("/ajax/", methods=("POST",))
        def ajax_submit():
            form = MyForm()
            if form.validate_on_submit():
                return jsonify(name=form.name.data,
                               success=True,
                               errors=None)

            return jsonify(name=None, 
                           errors=form.errors,
                           success=False)

        
        return app

class TestFileUpload(TestCase):

    def create_app(self):

        class FileUploadForm(Form):

            upload = FileField("Upload file")

        class MultipleFileUploadForm(Form):

            uploads = FieldList(FileField("upload"), min_entries=3)


        app = super(TestFileUpload, self).create_app()
        app.config['CSRF_ENABLED'] = False

        @app.route("/upload-multiple/", methods=("POST",))
        def upload_multiple():
            form = MultipleFileUploadForm()
            if form.validate_on_submit():
                for upload in form.uploads.entries:
                    assert upload.file is not None

            return Response("OK")


        @app.route("/upload/", methods=("POST",))
        def upload():
            form = FileUploadForm()
            if form.validate_on_submit():

                filedata = form.upload.file
            
            else:
                
                filedata = None

            return render_template("upload.html",
                                   filedata=filedata,
                                   form=form)
        
        return app


    def test_multiple_files(self):

        fps = [self.app.open_resource("flask.png") for i in xrange(3)]
        data = [("uploads-%d" % i, fp) for i, fp in enumerate(fps)] 
        response = self.client.post("/upload-multiple/", data=dict(data))
        assert response.status_code == 200

    def test_valid_file(self):
        
        with self.app.open_resource("flask.png") as fp:
            response = self.client.post("/upload/", 
                data={'upload' : fp})

        assert "flask.png</h3>" in response.data

    def test_invalid_file(self):
        
        response = self.client.post("/upload/", 
                data={'upload' : 'flask.png'})

        assert "flask.png</h3>" not in response.data

class TestValidateOnSubmit(TestCase):

    def test_not_submitted(self):

        response = self.client.get("/")
        assert 'DANNY' not in response.data

    def test_submitted_not_valid(self):

        self.app.config['CSRF_ENABLED'] = False

        response = self.client.post("/", data={})

        assert 'DANNY' not in response.data

    def test_submitted_and_valid(self):
        
        self.app.config['CSRF_ENABLED'] = False

        response = self.client.post("/", data={"name" : "danny"})
        print response.data

        assert 'DANNY' in response.data


class TestHiddenTag(TestCase):

    def test_hidden_tag(self):

        response = self.client.get("/hidden/")
        assert response.data.count('type="hidden"') == 5
        assert 'name="_method"' in response.data


class TestCSRF(TestCase):

    def test_csrf_token(self):

        response = self.client.get("/")
        assert '<div style="display:none;"><input id="csrf" name="csrf" type="hidden" value' in response.data
    
    def test_invalid_csrf(self):

        response = self.client.post("/", data={"name" : "danny"})
        assert 'DANNY' not in response.data
        assert "Missing or invalid CSRF token" in response.data

    def test_csrf_disabled(self):
        
        self.app.config['CSRF_ENABLED'] = False

        response = self.client.post("/", data={"name" : "danny"})
        assert 'DANNY' in response.data

    def test_validate_twice(self):

        response = self.client.post("/simple/", data={})
        self.assert_200(response)

    def test_ajax(self):

        response = self.client.post("/ajax/", 
                                    data={"name" : "danny"},
                                    headers={'X-Requested-With' : 'XMLHttpRequest'})
        
        assert response.status_code == 200

    def test_valid_csrf(self):

        response = self.client.get("/")
        pattern = re.compile(r'name="csrf" type="hidden" value="([0-9a-zA-Z-]*)"')
        match = pattern.search(response.data)
        assert match

        csrf_token = match.groups()[0]

        response = self.client.post("/", data={"name" : "danny", 
                                               "csrf" : csrf_token})

        assert "DANNY" in response.data

