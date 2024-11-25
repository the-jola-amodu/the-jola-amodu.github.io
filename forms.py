from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, FileField
from wtforms.validators import DataRequired, Length, ValidationError
from flask_ckeditor import CKEditorField


class PostForm(FlaskForm):
    title = StringField('Title')
    content = CKEditorField('Content', validators=[DataRequired()])
    media = FileField('Upload media')
    submit = SubmitField('Upload')


class EntranceForm(FlaskForm):
    pass_phrase = StringField('Pass Phrase', validators=[DataRequired()])

