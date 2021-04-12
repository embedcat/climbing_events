from openpyxl import Workbook, load_workbook
from openpyxl.writer.excel import save_virtual_workbook

from events import services
from events.models import Event


def load_template(filename: str) -> Workbook or None:
    try:
        return load_workbook(filename=filename)
    except FileNotFoundError:
        return None


def export_participants_to_start_list(event: Event):
    ROW_OFFSET = 8
    book = load_workbook(filename='static/events/xl_templates/startlist_template.xlsx')
    sheet = book.active
    sheet.cell(row=1, column=1).value = 'Скалодром "МАССИВ"'
    sheet.cell(row=2, column=1).value = event.title
    sheet.cell(row=3, column=7).value = event.date
    for set_no in range(event.set_num):
        sheet = book.copy_worksheet(book.worksheets[0])
        sheet.title = f'Сет {set_no + 1}'
        sheet.cell(row=5, column=1).value = sheet.title
        for index, p in enumerate(event.participant.filter(set_index=set_no).order_by('last_name')):
            sheet.cell(row=ROW_OFFSET + index, column=1).value = index + 1
            sheet.cell(row=ROW_OFFSET + index, column=2).value = f'{p.last_name} {p.first_name}'
            sheet.cell(row=ROW_OFFSET + index, column=3).value = p.birth_year
            sheet.cell(row=ROW_OFFSET + index, column=4).value = p.gender
            sheet.cell(row=ROW_OFFSET + index, column=5).value = p.city
            sheet.cell(row=ROW_OFFSET + index, column=6).value = p.team
            group_list = services.get_group_list(event=event)
            sheet.cell(row=ROW_OFFSET + index, column=7).value = group_list[p.group_index] if group_list != [] else ''
    # book.save(filename='startlist.xlsx')
    book.remove(book.worksheets[0])
    book.close()

    return save_virtual_workbook(book)
